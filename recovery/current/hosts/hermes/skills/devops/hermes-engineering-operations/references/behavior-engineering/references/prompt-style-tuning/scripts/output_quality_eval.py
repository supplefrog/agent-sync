"""V2 proposal for Hermes final-answer style evals.

Temp-only. Does not modify Hermes config/skills.

Meaningful changes vs output_quality_eval.py:
- richer prompt suite with explicit anti-overcompression cases
- per-prompt weighted rubrics instead of all checks = 1 point
- separates length, usefulness, task focus, and regression signals
- supports repeats to expose stochastic wins/losses
- stores full artifacts plus summary with win margins
- has self-test mode so grader changes can be validated without model calls
"""
from __future__ import annotations

import argparse, json, os, re, shutil, statistics, subprocess, sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML required: pip install pyyaml") from exc

REAL_HOME = Path(os.environ.get("REAL_HERMES_HOME", r"{{agent-signal:HERMES_HOME}}"))
BASE = Path(os.environ.get("HERMES_STYLE_EVAL_DIR", r"{{agent-signal:HOME}}/AppData/Local/Temp/hermes-output-quality-eval-v2-proposal"))
ANSI = re.compile(r"\x1b\[[0-9;]*m")
FOLLOWUP = ["want me", "would you like", "let me know", "if you want"]
BAD_OPENERS = ("it depends", "there are", "sure", "certainly", "great question", "here are")

# Each case says what good means. This reduces keyword-gaming and catches over-terse dumbness.
CASES: list[dict[str, Any]] = [
    {
        "id": "simple_fact_no_padding",
        "prompt": "What command shows my current git branch?",
        "max_words": 12,
        "must_any": ["git branch", "git status", "git rev-parse"],
        "forbid": ["modern git", "you can also", "want me"],
        "weights": {"answer_first": 2, "length_ok": 2, "required_signal": 3, "no_generic_followup": 2, "not_meta": 1},
    },
    {
        "id": "decision_with_mechanism",
        "prompt": "Should our 3-person startup build custom auth before launch in 2 weeks, or use hosted auth? Give the practical call.",
        "max_words": 120,
        "must_any": ["hosted", "clerk", "supabase", "firebase", "auth0"],
        "must_all_any": [["2 weeks", "launch", "small team", "3-person"], ["risk", "security", "time", "maintenance"]],
        "forbid": ["it depends", "comprehensive", "many factors", "want me"],
        "weights": {"answer_first": 2, "length_ok": 2, "required_signal": 2, "mechanism": 3, "no_bad_terms": 1, "no_generic_followup": 1, "not_meta": 1},
    },
    {
        "id": "pushback_not_coddling",
        "prompt": "We're behind, so I'm thinking delete the tests, rewrite the backend in Rust this weekend, and deploy Friday. Good plan?",
        "max_words": 130,
        "must_any": ["no", "bad", "risky", "don't", "do not"],
        "must_all_any": [["tests", "rewrite", "rust"], ["ship", "scope", "fix", "small", "rollback"]],
        "forbid": ["exciting", "great idea", "totally", "want me"],
        "weights": {"answer_first": 3, "length_ok": 2, "required_signal": 2, "mechanism": 2, "no_bad_terms": 2, "no_generic_followup": 1},
    },
    {
        "id": "dont_overcompress_explanation",
        "prompt": "Explain why OAuth is usually safer than rolling password auth, but keep it short enough for a startup decision.",
        "min_words": 45,
        "max_words": 140,
        "must_any": ["password", "token", "security", "breach", "reset", "mfa"],
        "must_all_any": [["hosted", "provider", "oauth"], ["less", "reduce", "avoid", "offload"]],
        "forbid": ["comprehensive", "deep dive", "want me"],
        "weights": {"answer_first": 1, "length_ok": 2, "not_too_short": 3, "required_signal": 2, "mechanism": 3, "no_generic_followup": 1},
    },
    {
        "id": "brainstorm_bounded",
        "prompt": "Brainstorm ways to make Hermes feel less verbose without making it dumb or under-explained.",
        "min_words": 50,
        "max_words": 180,
        "must_any": ["mode", "eval", "decision", "budget", "prompt", "verbosity", "concise"],
        "forbid": ["phase 1", "phase 2", "implementation plan", "want me"],
        "weights": {"answer_first": 1, "length_ok": 3, "required_signal": 2, "concrete": 3, "no_bad_terms": 1, "no_generic_followup": 1},
    },
    {
        "id": "stay_on_course_recovery",
        "prompt": "We were tuning final-answer verbosity. I mentioned you created an eval harness and were about to compare outputs. What should you do next?",
        "max_words": 90,
        "must_any": ["find", "locate", "run", "compare", "verify", "relevance"],
        "forbid": ["template", "skill packaging", "career-ops", "surface-eval", "want me"],
        "weights": {"answer_first": 2, "length_ok": 2, "required_signal": 3, "no_bad_terms": 2, "no_generic_followup": 1, "not_meta": 1},
    },
]

VARIANTS = {
    "current": None,
    # Candidate for strong models: preserves concise defaults without forcing exact
    # bullet counts or word caps that can suppress useful mechanisms/tradeoffs.
    "soft_budget_candidate": "Final-answer style: default concise. Put the recommendation or direct answer first. Include only the mechanism/tradeoff needed for the decision. For simple facts, answer in one line. For audits, debugging, research, and broad tradeoffs, use as much structure as needed but no filler. In brainstorming, give concrete ideas or constraints; do not force a fixed bullet count. Do not add generic follow-up offers or rhetorical closers.",
}


def clean(text: str) -> str:
    return ANSI.sub("", text).replace("Warning: Unknown toolsets: none", "").strip()


def words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def tail(text: str, n=2) -> str:
    lines = [x.strip().lower() for x in text.splitlines() if x.strip()]
    return "\n".join(lines[-n:])


def has_followup_closer(text: str) -> bool:
    t = tail(text)
    return any(x in t for x in FOLLOWUP)


def any_group_hit(text: str, groups: list[list[str]]) -> bool:
    low = text.lower()
    return all(any(term.lower() in low for term in group) for group in groups)


def line_count(text: str) -> int:
    return len([x for x in text.splitlines() if x.strip()])


def grade_answer(answer: str, spec: dict[str, Any], exit_code: int = 0) -> dict[str, Any]:
    text = clean(answer)
    low = text.lower()
    wc = words(text)
    first = next((ln.strip().lower() for ln in text.splitlines() if ln.strip()), "")
    forbid_hits = [t for t in spec.get("forbid", []) if t.lower() in low and not (t.lower() in FOLLOWUP and not has_followup_closer(text))]
    must_any = spec.get("must_any") or []
    weights = spec["weights"]
    raw_checks = {
        "exit_ok": exit_code == 0 and bool(text),
        "answer_first": not first.startswith(BAD_OPENERS),
        "length_ok": spec.get("min_words", 0) <= wc <= spec.get("max_words", 10_000),
        "not_too_short": wc >= spec.get("min_words", 0),
        "required_signal": True if not must_any else any(t.lower() in low for t in must_any),
        "mechanism": any_group_hit(text, spec.get("must_all_any", [])),
        "concrete": line_count(text) >= 4 or any(ch in text for ch in [":", ";", "-", "•"]),
        "no_bad_terms": not forbid_hits,
        "no_generic_followup": not has_followup_closer(text),
        "not_meta": "i should" not in low and "the user" not in low,
    }
    active = {k: raw_checks[k] for k in weights}
    score = sum(weights[k] for k, ok in active.items() if ok)
    max_score = sum(weights.values())
    return {"score": score, "max_score": max_score, "word_count": wc, "checks": active, "forbid_hits": forbid_hits}


def make_home(variant: str, overlay: str | None) -> Path:
    home = BASE / "homes" / variant
    home.mkdir(parents=True, exist_ok=True)
    for name in ["config.yaml", ".env", "auth.json", "SOUL.md"]:
        src = REAL_HOME / name
        if src.exists(): shutil.copy2(src, home / name)
    cfg_path = home / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg.setdefault("display", {})["show_reasoning"] = False
    cfg.setdefault("display", {}).setdefault("sections", {})["thinking"] = "hidden"
    if overlay:
        cfg.setdefault("agent", {})["system_prompt"] = (cfg.setdefault("agent", {}).get("system_prompt", "") + "\n" + overlay).strip()
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return home


def run_one(variant: str, home: Path, case: dict[str, Any], rep: int) -> dict[str, Any]:
    out_dir = BASE / "runs" / variant / f"rep{rep}" / case["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["HERMES_DISABLE_UPDATE_CHECK"] = "1"
    p = subprocess.run(["hermes", "chat", "-q", case["prompt"], "-Q"], cwd=out_dir, env=env, text=True, capture_output=True, timeout=260)
    ans = clean(p.stdout)
    (out_dir / "stdout.txt").write_text(ans, encoding="utf-8", errors="replace")
    (out_dir / "stderr.txt").write_text(p.stderr, encoding="utf-8", errors="replace")
    return {"variant": variant, "rep": rep, "id": case["id"], "exit": p.returncode, "answer": ans, "grade": grade_answer(ans, case, p.returncode)}


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for variant in VARIANTS:
        rs = [r for r in rows if r["variant"] == variant]
        scores = [r["grade"]["score"] for r in rs]
        maxes = [r["grade"]["max_score"] for r in rs]
        words_ = [r["grade"]["word_count"] for r in rs]
        by_case = {}
        for case in CASES:
            cr = [r for r in rs if r["id"] == case["id"]]
            by_case[case["id"]] = {
                "avg_score": round(statistics.mean([r["grade"]["score"] for r in cr]), 2),
                "max_score": cr[0]["grade"]["max_score"] if cr else None,
                "avg_words": round(statistics.mean([r["grade"]["word_count"] for r in cr]), 1) if cr else None,
                "failures": [r["grade"]["checks"] for r in cr if r["grade"]["score"] < r["grade"]["max_score"]],
            }
        total = sum(scores)
        max_total = sum(maxes)
        out.append({
            "variant": variant,
            "score": total,
            "max_score": max_total,
            "score_rate": round(total / max_total, 4) if max_total else None,
            "avg_words": round(statistics.mean(words_), 1),
            "per_case": by_case,
        })
    baseline = next((x for x in out if x["variant"] == "current"), None)
    if baseline:
        for item in out:
            item["score_delta_vs_current"] = item["score"] - baseline["score"]
            item["word_delta_vs_current"] = round(item["avg_words"] - baseline["avg_words"], 1)
    return out


def self_test() -> None:
    good = "Use hosted auth. With two weeks and three people, rolling passwords adds security, reset, MFA, and maintenance risk you do not need before launch."
    bad = "It depends. There are many factors. I can provide a comprehensive breakdown if you want."
    g = grade_answer(good, CASES[1])
    b = grade_answer(bad, CASES[1])
    assert g["score"] > b["score"], (g, b)
    assert b["forbid_hits"], b
    terse_bad = "Use OAuth."
    t = grade_answer(terse_bad, CASES[3])
    assert not t["checks"].get("not_too_short", True), t
    print(json.dumps({"self_test": "ok", "good": g, "bad": b, "over_terse": t}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--repeats", type=int, default=1)
    args = ap.parse_args()
    if args.self_test:
        self_test(); return
    if BASE.exists(): shutil.rmtree(BASE, ignore_errors=True)
    (BASE / "runs").mkdir(parents=True)
    rows = []
    for variant, overlay in VARIANTS.items():
        home = make_home(variant, overlay)
        for rep in range(args.repeats):
            for case in CASES:
                print(f"RUN {variant} rep{rep} {case['id']}", flush=True)
                rows.append(run_one(variant, home, case, rep))
    (BASE / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    summary = summarize(rows)
    (BASE / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"base": str(BASE), "summary": summary}, indent=2))

if __name__ == "__main__":
    main()
