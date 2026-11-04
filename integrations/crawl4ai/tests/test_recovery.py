import hashlib
import json
import os
from pathlib import Path
import unittest

from recovery import enrich_scrape, recover_html

REDDIT = "https://www.reddit.com/r/test/comments/abc/title/"
IG = "https://www.instagram.com/nasa/"


def comment(cid="a", body="Parent text", children="", **attrs):
    props = {"thingid": "t1_" + cid, "author": "alice", "postid": "t3_abc",
             "permalink": f"/r/test/comments/abc/comment/{cid}/", **attrs}
    return "<shreddit-comment " + " ".join(f'{k}="{v}"' for k, v in props.items()) + (
        f'><div slot="comment"><p>{body}</p></div>{children}</shreddit-comment>')


def profile_script(user, query="adp_PolarisLoggedOutDesktopWWWProfilePageQuery"):
    data = {"require": [["RelayPrefetchedStreamCache", "next", [],
                        [query, {"data": {"user": user}}]]]}
    return '<script type="application/json" data-sjs>' + json.dumps(data) + '</script>'


class RecoveryTests(unittest.TestCase):
    def test_nested_comments_have_separate_body_and_exact_identity(self):
        child = comment("b", "Child answer", parentid="t1_a")
        out = recover_html(REDDIT, comment(children=child))
        self.assertEqual([c["id"] for c in out["comments"]], ["t1_a", "t1_b"])
        self.assertEqual(out["comments"][0]["body"], "Parent text")
        self.assertEqual(out["comments"][1]["parent_id"], "t1_a")
        self.assertEqual(out["comments"][0]["parent_id"], "t3_abc")
        self.assertEqual(out["comments"][0]["permalink"],
                         "https://www.reddit.com/r/test/comments/abc/comment/a/")
        self.assertEqual(out["comments"][0]["author"], "alice")

    def test_dedupe_removed_deleted_and_inert_content(self):
        html = comment(body='Hi<script>bad()</script><style>bad</style><template>bad</template> there')
        html += comment() + comment("b", "[removed]") + comment("c", "[deleted]")
        html += '<template>' + comment("inert") + '</template>'
        got = recover_html(REDDIT, html)["comments"]
        self.assertEqual(len(got), 3)
        self.assertEqual(got[0]["body"], "Hi there")
        self.assertEqual([c["status"] for c in got], ["visible", "removed", "deleted"])

    def test_ig_exact_counts_from_recognized_profile_json(self):
        user = {"username": "nasa", "full_name": "NASA", "biography": "Space & science",
                "follower_count": 1234567, "following_count": 90, "media_count": 4988,
                "bio_links": [{"url": "https://www.nasa.gov/", "title": "NASA"},
                              {"url": "javascript:alert(1)"}]}
        got = recover_html(IG, profile_script(user))["profile"]
        self.assertEqual(got["biography"], "Space & science")
        self.assertEqual(got["counts"]["followers"], {"value": 1234567, "approximate": False,
                         "source": "profile_json.follower_count"})
        self.assertEqual(got["counts"]["following"]["value"], 90)
        self.assertEqual(got["counts"]["posts"]["value"], 4988)
        self.assertEqual(got["links"], [{"url": "https://www.nasa.gov/", "title": "NASA"}])

    def test_ig_metadata_fallback_is_labelled_approximate(self):
        html = '<meta property="og:title" content="NASA (@nasa) • Instagram photos and videos">'
        html += '<meta name="description" content="104M Followers, 94 Following, 4,988 Posts - NASA (@nasa) on Instagram: &quot;Space&quot;">'
        got = recover_html(IG, html)["profile"]
        self.assertEqual(got["name"], "NASA")
        self.assertEqual(got["biography"], "Space")
        self.assertEqual(got["counts"]["followers"]["value"], 104000000)
        self.assertTrue(got["counts"]["followers"]["approximate"])

    def test_unrelated_json_wrong_profile_and_posts_are_not_profiles(self):
        user = {"username": "nasa", "biography": "Wrong", "follower_count": 123}
        self.assertEqual(recover_html(IG, '<script type="application/json">' + json.dumps(user) + '</script>'), {})
        self.assertEqual(recover_html(IG, profile_script(user, "UnrelatedQuery")), {})
        self.assertEqual(recover_html(IG.replace("nasa", "other"), profile_script(user)), {})
        self.assertEqual(recover_html("https://www.instagram.com/p/xyz/", profile_script(user)), {})

    def test_hosts_errors_and_limits_fail_closed(self):
        html = comment()
        for url in ["https://reddit.com.evil.test/", "https://evilreddit.com/", "https://instagram.com.evil.test/nasa/", "file:///reddit.com", "https://reddit.com@evil.test/"]:
            self.assertEqual(recover_html(url, html), {})
        self.assertEqual(recover_html(REDDIT, "<title>You've been blocked by network security</title>" + html), {})
        self.assertEqual(recover_html(REDDIT, "x" * (5 * 1024 * 1024 + 1)), {})
        self.assertEqual(enrich_scrape(REDDIT, {"ok": False, "html": html}), {"ok": False, "html": html})
        self.assertEqual(enrich_scrape(REDDIT, {"ok": True, "status_code": 403, "html": html}),
                         {"ok": True, "status_code": 403, "html": html})

    def test_enrichment_preserves_source_and_is_idempotent(self):
        result = {"ok": True, "html": comment(), "markdown": "# Post", "engine": "stealth", "extra": {"x": 1}}
        before = json.dumps(result)
        got = enrich_scrape(REDDIT, result)
        self.assertEqual(json.dumps(result), before)
        self.assertEqual(got["html"], result["html"])
        self.assertEqual(got["original_markdown"], "# Post")
        self.assertIn("Parent text", got["markdown"])
        self.assertEqual(got, enrich_scrape(REDDIT, got))
        complete = {"ok": True, "html": comment(), "markdown": "# Post\n\nParent text"}
        self.assertEqual(enrich_scrape(REDDIT, complete)["markdown"], complete["markdown"])
        self.assertEqual(enrich_scrape("https://example.com", result), result)
        self.assertEqual(got["html_recovery"]["provenance"]["html_sha256"], hashlib.sha256(result["html"].encode()).hexdigest())

    def test_linked_reddit_streamed_dom_but_not_arbitrary_template(self):
        fragment = '<template for="s_123_1">' + comment() + '</template>'
        placeholder = '<suspense-placeholder id="s_123_1" name="TopComments"></suspense-placeholder>'
        replace = '<suspense-replace target="#s_123_1" template="template[for=s_123_1]"></suspense-replace>'
        self.assertEqual(recover_html(REDDIT, fragment), {})
        self.assertEqual(recover_html(REDDIT, placeholder + fragment), {})
        self.assertEqual(recover_html(REDDIT, replace + fragment), {})
        got = recover_html(REDDIT, placeholder + fragment + replace)
        self.assertEqual(got["comments"][0]["body"], "Parent text")

    def test_partial_missing_comments_only_appended(self):
        out = enrich_scrape(REDDIT, {"ok": True, "html": comment() + comment("b", "Second body"),
                                   "markdown": "Parent text"})
        self.assertEqual(out["markdown"].count("Parent text"), 1)
        self.assertEqual(out["markdown"].count("Second body"), 1)

    def test_explicit_metadata_counts_and_conflicting_json_preserved(self):
        user = {"username": "nasa", "biography": "Space", "follower_count": 104426607,
                "following_count": 90}
        html = '<meta property="og:title" content="NASA (@nasa) • Instagram">'
        html += '<meta name="description" content="104M Followers, 94 Following, 4,988 Posts - NASA (@nasa)">'
        recovered = recover_html(IG, html + profile_script(user))
        counts = recovered["profile"]["counts"]
        self.assertTrue(counts["following"]["conflict"])
        self.assertEqual([o["value"] for o in counts["following"]["observations"]], [94, 90])
        self.assertFalse(counts["posts"]["approximate"])
        self.assertTrue(any("Conflicting following" in w for w in recovered["provenance"]["warnings"]))

    def test_limits_depth_nodes_comments_and_long_body(self):
        self.assertEqual(recover_html(REDDIT, '<div>' * 300 + comment() + '</div>' * 300), {})
        self.assertEqual(recover_html(REDDIT, '<br>' * 100001 + comment()), {})
        got = recover_html(REDDIT, ''.join(comment(str(i), "x" * 13000) for i in range(21)))
        self.assertLessEqual(sum(len(c["body"]) for c in got["comments"]), 250000)
        self.assertTrue(all(len(c["body"]) <= 12000 for c in got["comments"]))
        got = recover_html(REDDIT, ''.join(comment(str(i), "body") for i in range(501)))
        self.assertEqual(len(got["comments"]), 500)

    def test_complete_ig_markdown_not_duplicated_and_no_network_needed(self):
        user = {"username": "nasa", "full_name": "NASA", "biography": "Space science",
                "follower_count": 1234, "following_count": 90, "media_count": 20}
        text = "NASA (@nasa)\nSpace science\n1,234 followers, 90 following, 20 posts"
        out = enrich_scrape(IG, {"ok": True, "html": profile_script(user), "markdown": text})
        self.assertEqual(out["markdown"], text)

    @unittest.skipUnless(os.environ.get("RECOVERY_FIXTURES"), "local raw fixtures not distributed")
    def test_real_saved_api_results(self):
        root = Path(os.environ["RECOVERY_FIXTURES"])
        ig = json.loads((root / "instagram-profile.json").read_text(encoding="utf8"))
        rd = json.loads((root / "reddit-thread-second.json").read_text(encoding="utf8"))
        profile = recover_html(ig["url"], ig["body"]["html"])["profile"]
        self.assertEqual(profile["username"], "nasa")
        self.assertEqual(profile["biography"], "Making the seemingly impossible, possible. ✨")
        self.assertEqual(profile["counts"]["followers"]["value"], 104426607)
        self.assertEqual(profile["counts"]["following"]["value"], 90)
        comments = recover_html(rd["url"], rd["body"]["html"])["comments"]
        self.assertEqual(len(comments), 25)
        self.assertEqual(len({c["id"] for c in comments}), 25)
        self.assertEqual(sum(c["source_state"] == "deferred_dom_fragment" for c in comments), 18)
        self.assertEqual(comments[0]["id"], "t1_jb3ast5")
        self.assertEqual(comments[0]["author"], "robvas")
        self.assertNotIn(comments[0]["body"], rd["body"]["markdown"])
        by_id = {c["id"]: c for c in comments}
        self.assertEqual(by_id["t1_jb6jck6"]["parent_id"], "t1_jb3aq6q")
        self.assertNotIn(by_id["t1_jb6jck6"]["body"], by_id["t1_jb3aq6q"]["body"])


if __name__ == "__main__":
    unittest.main()
