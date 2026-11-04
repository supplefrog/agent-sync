"""Pure, bounded recovery of public content omitted by a markdown extractor.

This does not fetch, execute scripts, establish completeness, or bypass gates.
Only recognized public profile data and rendered Reddit comment slots are used.
"""

import hashlib
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit

VERSION = "public-html-v1"
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_NODES = 100_000
MAX_DEPTH = 256
MAX_COMMENTS = 500
MAX_TEXT = 12_000
MAX_OUTPUT_TEXT = 250_000
_VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
_INERT = frozenset(("script", "style", "template", "noscript", "svg"))
_REDDIT = frozenset(("reddit.com", "www.reddit.com", "old.reddit.com", "new.reddit.com", "np.reddit.com", "m.reddit.com", "sh.reddit.com"))
_INSTAGRAM = frozenset(("instagram.com", "www.instagram.com", "m.instagram.com"))
_BLOCK = re.compile(r"blocked by network security|access denied|verify (?:you are|you're) human|security verification|just a moment|page (?:isn't|is not) available", re.I)


class _Limit(ValueError):
    pass


class _Node:
    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]
        self.nodes = 0

    def _count(self):
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise _Limit("node limit")

    def handle_starttag(self, tag, attrs):
        self._count()
        if len(self.stack) > MAX_DEPTH:
            raise _Limit("depth limit")
        node = _Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self._count()
        self.stack[-1].children.append(data)


def _nodes(root, include_scripts=False):
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, str):
            continue
        yield node
        if node.tag not in _INERT or (include_scripts and node.tag == "script"):
            stack.extend(reversed(node.children))


def _text(root, prune_comments=False):
    parts = []
    remaining = MAX_TEXT
    stack = [root]
    while stack and remaining > 0:
        node = stack.pop()
        if isinstance(node, str):
            parts.append(node[:remaining])
            remaining -= len(node[:remaining])
        elif node.tag not in _INERT and not (prune_comments and node is not root and node.tag == "shreddit-comment"):
            if node.tag in ("p", "div", "br", "li", "blockquote", "pre"):
                parts.append(" ")
            stack.extend(reversed(node.children))
    return " ".join("".join(parts).split())


def _http_link(value, base):
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        full = urljoin(base, value)
        parsed = urlsplit(full)
        if parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username and not parsed.password:
            return full
    except ValueError:
        pass
    return None


def _json_nodes(value):
    stack = [(value, "$", 0)]
    count = 0
    while stack:
        item, path, depth = stack.pop()
        count += 1
        if count > 50_000 or depth > 64:
            raise _Limit("JSON limit")
        yield item, path
        if isinstance(item, dict):
            stack.extend((v, path + "." + str(k)[:100], depth + 1) for k, v in item.items())
        elif isinstance(item, list):
            stack.extend((v, path + "[" + str(i) + "]", depth + 1) for i, v in enumerate(item))


def _reddit(root, url):
    comments, seen = [], set()
    # Reddit streams DOM fragments after </html>. Accept only its linked
    # TopComments placeholder/template/replace triple, never arbitrary templates.
    ordinary_nodes = list(_nodes(root))
    placeholders = {n.attrs.get("id") for n in ordinary_nodes
                    if n.tag == "suspense-placeholder" and n.attrs.get("name") == "TopComments"
                    and re.fullmatch(r"s_[0-9]+_[0-9]+", n.attrs.get("id", ""))}
    replace_ids = {n.attrs.get("target", "")[1:] for n in ordinary_nodes if n.tag == "suspense-replace"
                   and n.attrs.get("target", "").startswith("#")
                   and n.attrs.get("template") == "template[for=" + n.attrs.get("target", "")[1:] + "]"}
    streamed = [n for n in ordinary_nodes if n.tag == "template" and n.attrs.get("for") in placeholders & replace_ids]
    allowed_templates = {id(n) for n in streamed}
    deferred_templates = set()
    # Only the known deferred-comments container under a captured comment tree.
    # _nodes intentionally does not enter templates, so include stream children.
    fragment_roots = [root] + [c for n in streamed for c in n.children if not isinstance(c, str)]
    for fragment in fragment_roots:
        for tree in _nodes(fragment):
            if tree.tag == "shreddit-comment-tree":
                for candidate in _nodes(tree):
                    if candidate.tag == "template" and candidate.attrs.get("id") == "deferred-comments":
                        deferred_templates.add(id(candidate))
    allowed_templates |= deferred_templates
    # Traverse with the nearest comment ancestor; attributes may omit parentid.
    stack = [(root, None, False)]
    total = 0
    while stack:
        node, ancestor, deferred = stack.pop()
        if isinstance(node, str) or (node.tag in _INERT and id(node) not in allowed_templates):
            continue
        current = ancestor
        deferred = deferred or id(node) in deferred_templates
        if node.tag == "shreddit-comment":
            attrs = node.attrs
            cid = attrs.get("thingid", attrs.get("id", ""))
            if re.fullmatch(r"t1_[a-z0-9]+", cid):
                current = cid
                slots = []
                pending = list(reversed(node.children))
                while pending:
                    child = pending.pop()
                    if isinstance(child, str) or child.tag in _INERT or child.tag == "shreddit-comment":
                        continue
                    if child.attrs.get("slot") == "comment":
                        slots.append(_text(child, prune_comments=True))
                    else:
                        pending.extend(reversed(child.children))
                body = " ".join(s for s in slots if s)[:MAX_TEXT]
                if body and cid not in seen and len(comments) < MAX_COMMENTS and total + len(body) <= MAX_OUTPUT_TEXT:
                    parent = attrs.get("parentid") or attrs.get("parent-id") or ancestor or attrs.get("postid")
                    if parent and not re.fullmatch(r"t[13]_[a-z0-9]+", parent):
                        parent = None
                    permalink = _http_link(attrs.get("permalink"), url)
                    if permalink and urlsplit(permalink).hostname not in _REDDIT:
                        permalink = None
                    status = body.lower().strip()
                    status = {"[removed]": "removed", "[deleted]": "deleted"}.get(status, "visible")
                    comments.append({"id": cid, "parent_id": parent,
                                     "author": (attrs.get("author") or "")[:256] or None,
                                     "permalink": permalink, "body": body, "status": status,
                                     "source_state": "deferred_dom_fragment" if deferred else "captured_dom_fragment",
                                     "source": 'shreddit-comment[thingid] [slot="comment"]'})
                    seen.add(cid)
                    total += len(body)
        stack.extend((child, current, deferred) for child in reversed(node.children))
    if not comments:
        return {}
    sources = ['shreddit-comment[thingid] [slot="comment"]']
    if streamed:
        sources.append('Linked suspense-placeholder[name=TopComments] + template[for] + suspense-replace DOM fragment; scripts not executed')
    if deferred_templates:
        sources.append('shreddit-comment-tree template[id=deferred-comments] captured deferred DOM; not proof of live mounting')
    return {"kind": "reddit_comments", "comments": comments, "sources": sources}


def _instagram(root, url, username):
    profile = {"username": username, "counts": {}, "links": []}
    sources = []
    meta = {n.attrs.get("property", n.attrs.get("name", "")): n.attrs.get("content", "")[:MAX_TEXT]
            for n in _nodes(root) if n.tag == "meta"}
    title = meta.get("og:title", "")
    # Metadata must identify this profile, not a generic login or unrelated page.
    if re.search(r"\(@" + re.escape(username) + r"\)", title, re.I):
        profile["name"] = title.split(" (@", 1)[0][:512]
        description = meta.get("description") or meta.get("og:description", "")
        if re.search(r"\(@" + re.escape(username) + r"\)", description, re.I):
            for field, label in (("followers", "Followers"), ("following", "Following"), ("posts", "Posts")):
                match = re.search(r"([\d,.]+)([KMB]?)\s+" + label + r"\b", description, re.I)
                if match:
                    number, suffix = match.groups()
                    try:
                        value = int(float(number.replace(",", "")) * {"": 1, "K": 1000, "M": 1_000_000, "B": 1_000_000_000}[suffix.upper()])
                        profile["counts"][field] = {"value": value, "approximate": bool(suffix or "." in number), "source": "meta.description"}
                    except (ValueError, OverflowError):
                        pass
            bio = re.search(r'on Instagram:\s*"(.*)"\s*$', description, re.S)
            if bio:
                profile["biography"] = bio.group(1)[:MAX_TEXT]
            sources.append("meta[property=og:title], meta[name=description], meta[property=og:description]")
    for script in _nodes(root):
        if script.tag != "script" or script.attrs.get("type") != "application/json" or "data-sjs" not in script.attrs:
            continue
        raw = "".join(c for c in script.children if isinstance(c, str))
        if len(raw) > 512_000:
            continue
        try:
            payload = json.loads(raw)
            # Restrict traversal to Relay's explicitly named logged-out profile query.
            for item, path in _json_nodes(payload):
                if not (isinstance(item, list) and len(item) >= 4 and item[:2] == ["RelayPrefetchedStreamCache", "next"]):
                    continue
                args = item[3]
                if not (isinstance(args, list) and len(args) >= 2 and isinstance(args[0], str)
                        and re.fullmatch(r"(?:adp_)?PolarisLoggedOut(?:Desktop|Mobile)WWWProfile(?:Page|RootContentQuery)[A-Za-z0-9_]*", args[0])):
                    continue
                for user, user_path in _json_nodes(args[1]):
                    if not (isinstance(user, dict) and str(user.get("username", "")).lower() == username.lower()
                            and "biography" in user and ("follower_count" in user or "edge_followed_by" in user)):
                        continue
                    for source, target in (("full_name", "name"), ("biography", "biography")):
                        if isinstance(user.get(source), str):
                            profile[target] = user[source][:MAX_TEXT]
                    for target, keys in (("followers", ("follower_count", "edge_followed_by")),
                                         ("following", ("following_count", "edge_follow")),
                                         ("posts", ("media_count", "edge_owner_to_timeline_media"))):
                        for key in keys:
                            value = user.get(key)
                            if isinstance(value, dict):
                                value = value.get("count")
                            if type(value) is int and 0 <= value <= 10**15:
                                previous = profile["counts"].get(target)
                                profile["counts"][target] = {"value": value, "approximate": False, "source": "profile_json." + key}
                                if previous:
                                    observed = {k: v for k, v in profile["counts"][target].items()}
                                    profile["counts"][target]["observations"] = [previous, observed]
                                    if not previous["approximate"] and previous["value"] != value:
                                        profile["counts"][target]["conflict"] = True
                                break
                    links = user.get("bio_links", [])
                    if not isinstance(links, list):
                        links = []
                    links = links[:30] + [{"url": user.get("external_url"), "title": ""}]
                    for link in links:
                        if not isinstance(link, dict):
                            continue
                        href = _http_link(link.get("url"), url)
                        if href and not any(l["url"] == href for l in profile["links"]):
                            profile["links"].append({"url": href, "title": str(link.get("title") or "")[:512]})
                    sources.append("script[type=application/json][data-sjs] " + path + "[3][1]" + user_path[1:])
                    # One identified profile record is sufficient; do not combine
                    # arbitrary later records or create nested observations.
                    return {"kind": "instagram_profile", "profile": profile, "sources": sources}
        except (ValueError, RecursionError, _Limit):
            continue
    return {"kind": "instagram_profile", "profile": profile, "sources": sources} if sources else {}


def recover_html(url: str, html: str) -> dict:
    """Return recovered structured content with provenance, or {} if not eligible.

    Limits fail closed. No claim is made about unloaded comments, hidden content,
    profile freshness, or agreement between metadata and embedded JSON.
    """
    if not isinstance(url, str) or not isinstance(html, str) or len(html) > MAX_HTML_BYTES:
        return {}
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("https", "http") or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            return {}
        host = parsed.hostname
        if host not in _REDDIT | _INSTAGRAM:
            return {}
        match = re.fullmatch(r"/([A-Za-z0-9_.]{1,30})/?", parsed.path)
        if host in _INSTAGRAM and (not match or match[1].lower() in {"p", "reel", "reels", "stories", "explore", "accounts", "direct", "about", "developer"}):
            return {}
        raw = html.encode("utf-8")
        if len(raw) > MAX_HTML_BYTES:
            return {}
        parser = _Tree()
        parser.feed(html)
        parser.close()
        # Gate indicators are page headings/titles, not arbitrary comment text.
        if any(_BLOCK.search(_text(n)) for n in _nodes(parser.root) if n.tag in ("title", "h1")):
            return {}
        recovered = _reddit(parser.root, url) if host in _REDDIT else _instagram(parser.root, url, match[1])
        if not recovered:
            return {}
        sources = recovered.pop("sources", ['shreddit-comment[thingid] [slot="comment"]'])
        recovered["provenance"] = {"html_sha256": hashlib.sha256(raw).hexdigest(), "extraction_version": VERSION,
                                   "sources": sources, "warnings": ["Derived from supplied HTML; partial recovery only, not a completeness or freshness claim.",
                                   "Abbreviated metadata counts are approximate; integer counts are exact observations, not verified current values. JSON and metadata observations are retained when both exist."] if host in _INSTAGRAM else
                                   ["Derived from supplied HTML; only comment slots present in this DOM are recovered, not all comments."]}
        if host in _INSTAGRAM:
            for field, count in recovered["profile"]["counts"].items():
                if count.get("conflict"):
                    recovered["provenance"]["warnings"].append(f"Conflicting {field} observations in metadata and profile JSON; no authoritative current count established.")
        recovered["provenance"]["warnings"].append(f"Recovery limits: {MAX_COMMENTS} comments, {MAX_TEXT} characters per body/biography, {MAX_OUTPUT_TEXT} total recovered comment characters; long text may be truncated.")
        return recovered
    except (ValueError, RecursionError, _Limit):
        return {}


def _norm(text):
    return " ".join(text.split()).casefold()


def enrich_scrape(url: str, result: dict) -> dict:
    """Add recovery and only missing readable content to a successful scrape body.

    Original dictionary, raw HTML and original markdown are never mutated.
    Existing recovery is left alone to make repeated enrichment idempotent.
    """
    if not isinstance(result, dict) or result.get("ok") is not True or "html_recovery" in result:
        return result
    if any(isinstance(result.get(k), (int, float)) and result[k] >= 400 for k in ("status", "status_code", "http_status")):
        return result
    markdown = result.get("markdown", "")
    if not isinstance(markdown, str):
        return result
    recovered = recover_html(url, result.get("html"))
    if not recovered:
        return result
    original_norm = _norm(markdown)
    additions = []
    if recovered["kind"] == "reddit_comments":
        for c in recovered["comments"]:
            if _norm(c["body"]) not in original_norm:
                additions.append(f"Comment {c['id']} by {c['author'] or '[unknown]'} (parent: {c['parent_id'] or '[unknown]'}; {c['status']})\n{c['permalink'] or ''}\n\n{c['body']}")
    else:
        profile = recovered["profile"]
        for key, label in (("name", "Name"), ("username", "Username"), ("biography", "Biography")):
            value = profile.get(key)
            if value and _norm(value) not in original_norm:
                additions.append(f"{label}: {value}")
        for label, count in profile["counts"].items():
            source = "profile JSON observation" if count["source"].startswith("profile_json") else "metadata observation"
            line = f"{label.title()}: {count['value']:,}" + (" (approximate, metadata)" if count["approximate"] else f" ({source})")
            if count.get("conflict"):
                line += "; conflicting source observations: " + ", ".join(f"{c['value']:,} ({c['source']})" for c in count["observations"])
            # Count and label must both be present; a username substring is not enough.
            number = r"(?:" + re.escape(f"{count['value']:,}") + "|" + str(count["value"]) + ")"
            covered = re.search(r"\b" + re.escape(label) + r"\s*:?\s*" + number + r"\b|\b" + number + r"\s+" + re.escape(label) + r"\b", markdown, re.I)
            # A conflict is additional information even if the preferred candidate
            # count already appears in markdown.
            if not covered or count.get("conflict"):
                additions.append(line)
        for link in profile["links"]:
            if link["url"] not in markdown:
                additions.append(f"{link['title'] or 'Public link'}: {link['url']}")
    output = dict(result)
    output["html_recovery"] = recovered
    if additions:
        output.setdefault("original_markdown", markdown)
        supplement = "\n\n## Recovered public HTML content (partial)\n\n" + "\n\n".join(additions)
        output["markdown"] = markdown + supplement[:MAX_OUTPUT_TEXT]
    return output
