#!/usr/bin/env python
"""Cheap pre-run gate for the github-follow-up skill.

The script inventories recently active authored issues, all open authored PRs,
and recently changed authored PRs through terminal outcomes. It fingerprints
the state that matters for follow-up and emits Hermes cron's
{"wakeAgent": ...} protocol. State is acknowledged explicitly after the agent
finishes so failed runs retry instead of silently consuming changes.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


GRAPHQL_PR_THREADS = r"""
query($owner:String!,$name:String!,$number:Int!,$threadCursor:String){
  repository(owner:$owner,name:$name){
    pullRequest(number:$number){
      mergeable
      reviewDecision
      reviewThreads(first:100,after:$threadCursor){
        totalCount
        pageInfo{hasNextPage endCursor}
        nodes{
          id isResolved isOutdated path line originalLine
          comments(first:100){
            totalCount
            pageInfo{hasNextPage endCursor}
            nodes{id databaseId author{login} createdAt updatedAt body url replyTo{id}}
          }
        }
      }
    }
  }
}
"""

GRAPHQL_THREAD_COMMENTS = r"""
query($threadId:ID!,$commentCursor:String){
  node(id:$threadId){
    ... on PullRequestReviewThread{
      comments(first:100,after:$commentCursor){
        totalCount
        pageInfo{hasNextPage endCursor}
        nodes{id databaseId author{login} createdAt updatedAt body url replyTo{id}}
      }
    }
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lookback-days", type=int, default=45)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--ack", metavar="FINGERPRINT")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def hermes_home() -> Path:
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"]).expanduser()
    if os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "hermes"
    return Path.home() / ".hermes"


def run_gh(args: list[str]) -> Any:
    proc = subprocess.run(
        ["gh", *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown gh failure"
        raise RuntimeError(f"gh {' '.join(args[:3])} failed: {detail}")
    text = proc.stdout.strip()
    return json.loads(text) if text else None


def body_digest(value: str | None) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]


def login_of(author: Any) -> str | None:
    return author.get("login") if isinstance(author, dict) else None


def event_time(item: dict[str, Any]) -> str:
    return item.get("updatedAt") or item.get("submittedAt") or item.get("createdAt") or ""


def normalized_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": comment.get("id"),
        "author": login_of(comment.get("author")),
        "createdAt": comment.get("createdAt"),
        "updatedAt": comment.get("updatedAt"),
        "url": comment.get("url"),
        "bodyDigest": body_digest(comment.get("body")),
    }


def latest_event(events: list[dict[str, Any]], viewer: str | None = None) -> dict[str, Any] | None:
    eligible = [event for event in events if not viewer or event.get("author") != viewer]
    return max(eligible, key=event_time) if eligible else None


def inspect_issue(summary: dict[str, Any], viewer: str) -> dict[str, Any]:
    repo = summary["repository"]["nameWithOwner"]
    number = int(summary["number"])
    comments: list[dict[str, Any]] = []
    if int(summary.get("commentsCount") or 0) > 0:
        detail = run_gh([
            "issue", "view", str(number), "-R", repo,
            "--json", "comments",
        ])
        comments = [normalized_comment(item) for item in (detail.get("comments") or [])]
    latest = max(comments, key=event_time) if comments else None
    return {
        "kind": "issue",
        "key": f"issue:{repo}#{number}",
        "repo": repo,
        "number": number,
        "title": summary.get("title"),
        "url": summary.get("url"),
        "state": summary.get("state"),
        "updatedAt": summary.get("updatedAt"),
        "commentsCount": summary.get("commentsCount", 0),
        "latestComment": latest,
        "latestExternalComment": latest_event(comments, viewer),
    }


def normalize_check(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": check.get("__typename"),
        "name": check.get("name") or check.get("context"),
        "workflow": check.get("workflowName"),
        "status": check.get("status"),
        "conclusion": check.get("conclusion"),
        "state": check.get("state"),
        "detailsUrl": check.get("detailsUrl") or check.get("targetUrl"),
    }


def normalized_issue_ref(issue: dict[str, Any]) -> dict[str, Any]:
    repository = issue.get("repository") or {}
    repo = repository.get("nameWithOwner")
    number = issue.get("number")
    return {
        "key": f"issue:{repo}#{number}" if repo and number is not None else None,
        "repo": repo,
        "number": number,
        "url": issue.get("url"),
    }


def terminal_outcome(detail: dict[str, Any]) -> str | None:
    if detail.get("mergedAt") or detail.get("state") == "MERGED":
        return "merged"
    if detail.get("state") == "CLOSED":
        return "closed-unmerged"
    return None


def fetch_pr_graph(owner: str, name: str, number: int) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    nodes: list[dict[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    metadata: dict[str, Any] = {}
    total_count = 0

    while True:
        args = [
            "api", "graphql",
            "-F", f"owner={owner}",
            "-F", f"name={name}",
            "-F", f"number={number}",
        ]
        if cursor:
            args += ["-F", f"threadCursor={cursor}"]
        args += ["-f", f"query={GRAPHQL_PR_THREADS}"]
        graphql = run_gh(args)
        page_pr = (((graphql or {}).get("data") or {}).get("repository") or {}).get("pullRequest") or {}
        if not metadata:
            metadata = {
                "mergeable": page_pr.get("mergeable"),
                "reviewDecision": page_pr.get("reviewDecision"),
            }
        connection = page_pr.get("reviewThreads") or {}
        total_count = max(total_count, int(connection.get("totalCount") or 0))
        nodes.extend(connection.get("nodes") or [])
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor or cursor in seen:
            raise RuntimeError(f"invalid review-thread pagination cursor for {owner}/{name}#{number}")
        seen.add(cursor)

    return metadata, nodes, total_count


def fetch_all_thread_comments(thread: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    connection = thread.get("comments") or {}
    nodes = list(connection.get("nodes") or [])
    total_count = int(connection.get("totalCount") or len(nodes))
    page_info = connection.get("pageInfo") or {}
    cursor = page_info.get("endCursor")
    seen: set[str] = set()

    while page_info.get("hasNextPage"):
        if not cursor or cursor in seen:
            raise RuntimeError(f"invalid review-comment pagination cursor for thread {thread.get('id')}")
        seen.add(cursor)
        graphql = run_gh([
            "api", "graphql",
            "-F", f"threadId={thread['id']}",
            "-F", f"commentCursor={cursor}",
            "-f", f"query={GRAPHQL_THREAD_COMMENTS}",
        ])
        connection = (((graphql or {}).get("data") or {}).get("node") or {}).get("comments") or {}
        nodes.extend(connection.get("nodes") or [])
        total_count = max(total_count, int(connection.get("totalCount") or 0))
        page_info = connection.get("pageInfo") or {}
        cursor = page_info.get("endCursor")

    return nodes, total_count


def inspect_pr(summary: dict[str, Any], viewer: str) -> dict[str, Any]:
    repo = summary["repository"]["nameWithOwner"]
    owner, name = repo.split("/", 1)
    number = int(summary["number"])
    detail = run_gh([
        "pr", "view", str(number), "-R", repo,
        "--json",
        "state,isDraft,updatedAt,closedAt,mergedAt,mergeCommit,headRefName,headRefOid,baseRefName,"
        "mergeable,reviewDecision,closingIssuesReferences,comments,reviews,statusCheckRollup",
    ])

    comments = [normalized_comment(item) for item in (detail.get("comments") or [])]
    reviews: list[dict[str, Any]] = []
    for review in detail.get("reviews") or []:
        reviews.append({
            "id": review.get("id"),
            "author": login_of(review.get("author")),
            "state": review.get("state"),
            "submittedAt": review.get("submittedAt"),
            "commitOid": (review.get("commit") or {}).get("oid"),
            "bodyDigest": body_digest(review.get("body")),
        })

    outcome = terminal_outcome(detail)
    pr_graph: dict[str, Any] = {}
    thread_nodes: list[dict[str, Any]] = []
    thread_total_count = 0
    if outcome is None:
        pr_graph, thread_nodes, thread_total_count = fetch_pr_graph(owner, name, number)
    threads: list[dict[str, Any]] = []
    for thread in thread_nodes:
        raw_comments, comment_total_count = fetch_all_thread_comments(thread)
        thread_comments = [normalized_comment(item) for item in raw_comments]
        threads.append({
            "id": thread.get("id"),
            "isResolved": thread.get("isResolved"),
            "isOutdated": thread.get("isOutdated"),
            "path": thread.get("path"),
            "line": thread.get("line"),
            "originalLine": thread.get("originalLine"),
            "commentCount": comment_total_count,
            "commentsTruncated": False,
            "latestComment": max(thread_comments, key=event_time) if thread_comments else None,
        })

    events = list(comments)
    events.extend({
        "id": item.get("id"),
        "author": item.get("author"),
        "submittedAt": item.get("submittedAt"),
        "state": item.get("state"),
        "bodyDigest": item.get("bodyDigest"),
        "eventKind": "review",
    } for item in reviews)
    events.extend(
        {**thread["latestComment"], "eventKind": "review-thread"}
        for thread in threads if thread.get("latestComment")
    )

    checks = [normalize_check(item) for item in (detail.get("statusCheckRollup") or [])]
    check_counts: dict[str, int] = {}
    for check in checks:
        label = check.get("conclusion") or check.get("state") or check.get("status") or "UNKNOWN"
        check_counts[str(label)] = check_counts.get(str(label), 0) + 1

    return {
        "kind": "pr",
        "key": f"pr:{repo}#{number}",
        "repo": repo,
        "number": number,
        "title": summary.get("title"),
        "url": summary.get("url"),
        "state": detail.get("state"),
        "terminalOutcome": outcome,
        "isDraft": detail.get("isDraft"),
        "updatedAt": detail.get("updatedAt") or summary.get("updatedAt"),
        "closedAt": detail.get("closedAt"),
        "mergedAt": detail.get("mergedAt"),
        "mergeCommitOid": (detail.get("mergeCommit") or {}).get("oid"),
        "headRefName": detail.get("headRefName"),
        "headRefOid": detail.get("headRefOid"),
        "baseRefName": detail.get("baseRefName"),
        "relatedIssues": [
            normalized_issue_ref(item)
            for item in (detail.get("closingIssuesReferences") or [])
        ],
        "mergeable": pr_graph.get("mergeable") or detail.get("mergeable"),
        "reviewDecision": pr_graph.get("reviewDecision") or detail.get("reviewDecision"),
        "latestExternalEvent": latest_event(events, viewer),
        "unresolvedThreads": sum(1 for item in threads if not item.get("isResolved")),
        "reviewThreadCount": thread_total_count,
        "reviewThreadsTruncated": False,
        "threads": threads,
        "reviews": reviews,
        "comments": comments,
        "checkCounts": check_counts,
        "checks": checks,
    }


def collect(lookback_days: int, limit: int) -> dict[str, Any]:
    viewer_data = run_gh(["api", "user"])
    viewer = viewer_data["login"]
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=lookback_days)).date().isoformat()
    common_fields = "number,title,url,repository,updatedAt,state,commentsCount"
    issue_summaries = run_gh([
        "search", "issues", "--author", viewer, "--state", "open",
        "--updated", f">={since}", "--sort", "updated", "--order", "desc",
        "--limit", str(limit), "--json", common_fields,
    ]) or []
    open_pr_summaries = run_gh([
        "search", "prs", "--author", viewer, "--state", "open",
        "--sort", "updated", "--order", "desc",
        "--limit", str(limit), "--json", common_fields + ",isDraft",
    ]) or []
    recent_pr_summaries = run_gh([
        "search", "prs", "--author", viewer,
        "--updated", f">={since}", "--sort", "updated", "--order", "desc",
        "--limit", str(limit), "--json", common_fields + ",isDraft",
    ]) or []
    pr_summaries_by_key: dict[str, dict[str, Any]] = {}
    for item in [*open_pr_summaries, *recent_pr_summaries]:
        repo = item["repository"]["nameWithOwner"]
        pr_summaries_by_key[f"{repo}#{item['number']}"] = item
    pr_summaries = list(pr_summaries_by_key.values())

    items: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(inspect_issue, item, viewer) for item in issue_summaries]
        futures += [pool.submit(inspect_pr, item, viewer) for item in pr_summaries]
        for future in concurrent.futures.as_completed(futures):
            items.append(future.result())

    items.sort(key=lambda item: item["key"])
    truncated_sources = [
        name for name, summaries in (
            ("open-authored-issues", issue_summaries),
            ("open-authored-prs", open_pr_summaries),
            ("recent-authored-prs", recent_pr_summaries),
        )
        if len(summaries) >= limit
    ]
    return {
        "schema": 2,
        "viewer": viewer,
        "lookbackDays": lookback_days,
        "truncated": bool(truncated_sources),
        "truncatedSources": truncated_sources,
        "items": {item["key"]: item for item in items},
    }


def fingerprint(snapshot: dict[str, Any]) -> str:
    stable = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def changed_items(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    old_items = (previous or {}).get("snapshot", {}).get("items", {})
    new_items = current.get("items", {})
    changed: list[dict[str, Any]] = []
    first_run = previous is None

    for key, item in new_items.items():
        if first_run:
            changed.append(item)
        elif old_items.get(key) != item:
            changed.append(item)

    if not first_run:
        for key, old_item in old_items.items():
            if key not in new_items:
                changed.append({
                    "kind": old_item.get("kind"),
                    "key": key,
                    "repo": old_item.get("repo"),
                    "number": old_item.get("number"),
                    "title": old_item.get("title"),
                    "url": old_item.get("url"),
                    "removedFromTrackingScope": True,
                })
    if current.get("truncated"):
        changed.append({
            "kind": "inventory",
            "key": "inventory:truncated",
            "truncated": True,
            "truncatedSources": current.get("truncatedSources", []),
            "reason": "A search source hit the configured limit; complete paginated live discovery before acknowledging.",
        })
    return changed


def prompt_item(item: dict[str, Any]) -> dict[str, Any]:
    """Keep cron prompt context small; the agent must fetch live bodies anyway."""
    if item.get("kind") != "pr":
        return item
    compact = {
        key: value for key, value in item.items()
        if key not in {"threads", "reviews", "comments", "checks"}
    }
    compact["threadCount"] = len(item.get("threads", []))
    compact["reviewCount"] = len(item.get("reviews", []))
    compact["commentCount"] = len(item.get("comments", []))
    compact["attentionChecks"] = [
        check.get("name")
        for check in item.get("checks", [])
        if (check.get("conclusion") or check.get("state") or check.get("status"))
        not in {"SUCCESS", "SKIPPED", "NEUTRAL", "EXPECTED"}
    ]
    return compact


def emit(value: dict[str, Any], pretty: bool) -> None:
    print(json.dumps(value, indent=2 if pretty else None, ensure_ascii=False))


def main() -> int:
    args = parse_args()
    state_path = args.state or hermes_home() / "cache" / "github-follow-up" / "state.json"
    pending_path = state_path.with_name("pending.json")

    if args.ack:
        pending = read_json(pending_path)
        if not pending or pending.get("fingerprint") != args.ack:
            raise RuntimeError("refusing acknowledgement: pending fingerprint is missing or different")
        acknowledged = {
            "fingerprint": pending["fingerprint"],
            "acknowledgedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "snapshot": pending["snapshot"],
        }
        if not args.dry_run:
            write_json(state_path, acknowledged)
            pending_path.unlink(missing_ok=True)
        emit({"acknowledged": True, "fingerprint": args.ack}, args.pretty)
        return 0

    snapshot = collect(args.lookback_days, args.limit)
    current_fingerprint = fingerprint(snapshot)
    previous = read_json(state_path)
    changed = changed_items(previous, snapshot)

    if previous is None and not changed:
        baseline = {
            "fingerprint": current_fingerprint,
            "acknowledgedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "snapshot": snapshot,
        }
        if not args.dry_run:
            write_json(state_path, baseline)
        emit({"wakeAgent": False, "context": {"initializedBaseline": True}}, args.pretty)
        return 0

    if not changed and previous and previous.get("fingerprint") == current_fingerprint:
        emit({"wakeAgent": False}, args.pretty)
        return 0

    pending = {"fingerprint": current_fingerprint, "snapshot": snapshot}
    if not args.dry_run:
        write_json(pending_path, pending)

    script = Path(__file__).resolve()
    ack_command = (
        f'"{sys.executable}" "{script}" --state "{state_path.resolve()}" '
        f'--ack {current_fingerprint}'
    )
    emit({
        "wakeAgent": True,
        "context": {
            "kind": "github-follow-up-delta",
            "viewer": snapshot["viewer"],
            "fingerprint": current_fingerprint,
            "ackCommand": ack_command,
            "inventory": {
                "issuesAndPRs": len(snapshot["items"]),
                "changed": len(changed),
                "truncated": snapshot["truncated"],
                "truncatedSources": snapshot.get("truncatedSources", []),
            },
            "changed": [prompt_item(item) for item in changed],
        },
    }, args.pretty)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"github-follow-up gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
