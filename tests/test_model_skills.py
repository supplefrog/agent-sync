import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import model_skills as core

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("model_skill_hermes", ROOT / "integrations/model-skills/hermes/__init__.py")
hermes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hermes)
OPEN = ("openrouter", "openai/gpt-oss-120b")
CLOSED = ("openrouter", "anthropic/claude-sonnet-4")
TOOLS = [{"type": "function", "function": {"name": "skill_view"}}]


class ModelSkillsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "contracts").mkdir()
        (self.root / "skills/leanrea/references").mkdir(parents=True)
        (self.root / "skills/leanrea/SKILL.md").write_text("---\nname: leanrea\ndescription: Inspect selected shipped artifacts.\n---\nCANARY-BODY\n", encoding="utf-8")
        (self.root / "skills/leanrea/references/windows.md").write_text("CANARY-REFERENCE", encoding="utf-8")
        for name in ("skill-model-policy.json", "model-weights.json"):
            (self.root / "contracts" / name).write_bytes((ROOT / "contracts" / name).read_bytes())
        self.runtime = core.Runtime(self.root)
        self.adapter = hermes.Adapter(core, is_disabled=lambda name: False)
        self.adapter.runtime = self.runtime

    def context(self, n):
        return {"session_id": f"s{n}", "turn_id": f"t{n}", "api_request_id": f"a{n}"}

    def prepare(self, pair, context, request=None):
        return self.adapter.llm_request(request or {"model": pair[1], "tools": TOOLS, "messages": [{"role": "user", "content": "Inspect this file."}]}, provider=pair[0], model=pair[1], **context)["request"]

    def read(self, context, **args):
        return json.loads(self.adapter.tool_execution("skill_view", {"name": "leanrea", **args}, lambda _: json.dumps({"success":False,"error":"Skill 'leanrea' not found."}), **context))

    def test_same_adapter_closed_open_closed_and_reference(self):
        for n, pair, allowed in ((1, CLOSED, False), (2, OPEN, True), (3, CLOSED, False)):
            ctx = self.context(n)
            request = self.prepare(pair, ctx)
            self.assertEqual("leanrea:" in json.dumps(request), allowed)
            self.assertEqual(self.read(ctx)["success"], allowed)
        self.assertTrue(self.read(self.context(2), file_path="references/windows.md")["success"])

    def test_unknown_ids_and_codex_never_receive_the_skill(self):
        for pair in (("", OPEN[1]), ("unverified", OPEN[1]), (OPEN[0], "openai/gpt-oss-120b-lookalike"), ("openai", "gpt-6.1-sol"), ("anthropic", "claude-sonnet-4")):
            self.assertEqual(self.runtime.available("hermes", *pair), [])
            self.assertFalse(self.runtime.view("hermes", *pair, "leanrea")["success"])
        self.assertEqual(self.runtime.available("codex", *OPEN), [])

    def test_outbound_history_is_scrubbed_without_mutating_saved_history(self):
        loaded = self.runtime.view("hermes", *OPEN, "leanrea")["content"]
        request = {"model": CLOSED[1], "tools": TOOLS, "messages": [{"role": "tool", "content": json.dumps({"content": loaded})}, {"role": "user", "content": "Ordinary content remains."}]}
        before = copy.deepcopy(request)
        result = self.prepare(CLOSED, self.context(1), request)
        self.assertNotIn("CANARY-BODY", json.dumps(result))
        self.assertIn("Ordinary content remains.", json.dumps(result))
        self.assertEqual(request, before)
        ordinary = json.dumps({"model_scope": "open-weights", "name": "ordinary user data"})
        self.assertEqual(core.scrub(ordinary, set()), ordinary)
        self.assertIn("CANARY-BODY", json.dumps(self.prepare(OPEN, self.context(2), {**request, "model": OPEN[1]})))

    def test_concurrent_sessions_and_request_ids_are_isolated(self):
        def run(n):
            pair = OPEN if n % 2 else CLOSED
            ctx = self.context(n)
            self.prepare(pair, ctx)
            return self.read(ctx)["success"]
        with ThreadPoolExecutor(max_workers=6) as workers:
            self.assertEqual(list(workers.map(run, range(24))), [bool(n % 2) for n in range(24)])
        self.assertFalse(self.read({"session_id": "s1"})["success"])
        self.assertFalse(self.read({"session_id": "s1", "turn_id": "t1", "api_request_id": "a-other"})["success"])

    def test_native_skill_list_adds_only_eligible_entry_and_preserves_other_tools(self):
        base = json.dumps({"success": True, "skills": [{"name": "ordinary", "category": "general"}], "categories": ["general"], "count": 1})
        for n, pair in enumerate((CLOSED, OPEN)):
            ctx = self.context(n)
            self.prepare(pair, ctx)
            result = json.loads(self.adapter.tool_execution("skills_list", {}, lambda _: base, **ctx))
            self.assertEqual([r["name"] for r in result["skills"]], ["ordinary"] + (["leanrea"] if pair == OPEN else []))
        self.assertEqual(self.adapter.tool_execution("read_file", {"path": "x"}, lambda args: args), {"path": "x"})

    def test_corrupt_or_unknown_policy_fails_closed_and_invalidates_cache(self):
        self.assertTrue(self.runtime.available("hermes", *OPEN))
        p = self.root / "contracts/skill-model-policy.json"
        for value in ('{broken', '{"schema_version":99,"skills":{}}', '{"schema_version":1,"skills":{"leanrea":{"requires":"open-weights","hosts":"hermes"}}}'):
            p.write_text(value, encoding="utf-8")
            self.assertEqual(self.runtime.available("hermes", *OPEN), [])
        p.unlink()
        self.assertEqual(self.runtime.available("hermes", *OPEN), [])

    def test_reference_paths_cannot_escape_package(self):
        for relative in ("../SKILL.md", "/etc/passwd", "references/../../secret", "C:\\secret", "references//windows.md"):
            self.assertFalse(self.runtime.view("hermes", *OPEN, "leanrea", relative)["success"], relative)

    def test_wire_model_wins_over_stale_host_model(self):
        request = {"model": CLOSED[1], "messages": []}
        result = self.adapter.llm_request(request, provider=OPEN[0], model=OPEN[1], **self.context(1))["request"]
        self.assertNotIn("leanrea:", json.dumps(result))
        self.assertFalse(self.read(self.context(1))["success"])

    def test_native_tool_permissions_and_disabled_skills_are_preserved(self):
        ctx = self.context(1)
        self.prepare(OPEN, ctx)
        blocked = {"error": "Tool not allowed in this worker."}
        result = self.adapter.tool_execution("skill_view", {"name": "leanrea"}, lambda _: blocked, **ctx)
        self.assertEqual(result, blocked)
        self.adapter.is_disabled = lambda _: True
        result = self.prepare(OPEN, self.context(2))
        self.assertNotIn("leanrea:", json.dumps(result))
        self.assertFalse(self.read(self.context(2))["success"])
        self.adapter.is_disabled = lambda _: False
        result = self.prepare(OPEN, self.context(3), {"model": OPEN[1], "messages": [], "tools": []})
        self.assertNotIn("leanrea:", json.dumps(result))
        self.assertFalse(self.read(self.context(3))["success"])

    def test_generated_list_and_view_metadata_are_scrubbed_together(self):
        ctx = self.context(1)
        self.prepare(OPEN, ctx)
        base = json.dumps({"success": True, "skills": [{"name": "ordinary", "description": "keep", "category": "general"}], "count": 1, "categories": ["general"]})
        listed = self.adapter.tool_execution("skills_list", {}, lambda _: base, **ctx)
        viewed = json.dumps(self.read(ctx))
        messages = [{"role": "tool", "content": listed}, {"role": "tool", "content": viewed}, {"role": "user", "content": "I mentioned leanrea."}]
        request = {"model": CLOSED[1], "tools": TOOLS, "messages": messages}
        before = copy.deepcopy(request)
        result = self.prepare(CLOSED, self.context(2), request)
        self.assertNotIn("leanrea", json.dumps(result["messages"][:2]))
        self.assertEqual(json.loads(result["messages"][0]["content"])["skills"], [{"name": "ordinary", "description": "keep", "category": "general"}])
        self.assertEqual(result["messages"][2]["content"], "I mentioned leanrea.")
        self.assertEqual(request, before)

    def test_disable_after_request_is_rechecked_before_native_list_and_load(self):
        ctx = self.context(1)
        self.prepare(OPEN, ctx)
        self.adapter.is_disabled = lambda _: True
        base = json.dumps({"success": True, "skills": [{"name": "ordinary"}], "count": 1})
        result = self.adapter.tool_execution("skills_list", {}, lambda _: base, **ctx)
        self.assertEqual(result, base)
        self.assertFalse(self.read(ctx)["success"])


if __name__ == "__main__":
    unittest.main()
