"""No-model launcher regressions for the inline evaluator's runtime boundary."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime_evaluator", ROOT / "tools" / "eval.py")
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)
import evaluation_runtime as runtime
import evaluation_hermes_worker as hermes_worker


class EvaluationRuntimeTests(unittest.TestCase):
    def test_codex_requires_ordered_turn_and_completed_answer(self):
        thread = {"type": "thread.started", "thread_id": "11111111-1111-1111-1111-111111111111"}
        start = {"type": "turn.started"}
        answer = {"type": "item.completed", "item": {"id": "answer", "type": "agent_message", "text": "answer"}}
        complete = {"type": "turn.completed"}
        for rows in ([thread, complete], [thread, answer, start, complete], [thread, start, complete, answer],
                     [thread, start, answer, {"type": "error", "message": "native failure"}, complete]):
            with self.subTest(rows=rows):
                result = runtime.codex_events("\n".join(json.dumps(row) for row in rows), evaluator.extract_json)
                self.assertFalse(result["ok"])
        valid = runtime.codex_events("\n".join(json.dumps(row) for row in (thread, start, answer, complete)),
                                     evaluator.extract_json, expected_output="different answer")
        self.assertFalse(valid["ok"])

    def test_native_version_probe_is_bounded_and_drops_unrelated_output(self):
        calls = []
        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            self.assertNotIn("UNRELATED_API_KEY", kwargs["env"])
            return mock.Mock(returncode=0, stdout="UNRELATED_API_KEY=synthetic-secret\ncodex-cli 1.2.3\n", stderr="synthetic-secret")
        with mock.patch.dict(runtime.os.environ, {"PATH": "synthetic-path", "UNRELATED_API_KEY": "synthetic-secret"}, clear=True), \
             mock.patch.object(runtime, "native_executable", return_value="synthetic-native.exe"), \
             mock.patch.object(runtime.subprocess, "run", side_effect=fake_run):
            receipt = runtime.native_version("codex")
        self.assertTrue(receipt["ok"], receipt)
        self.assertEqual(receipt["version"], "codex 1.2.3")
        self.assertNotIn("synthetic-secret", json.dumps(receipt))
        self.assertEqual(calls[0][1]["timeout"], 10)
        self.assertFalse(Path(calls[0][1]["env"]["CODEX_HOME"]).exists())

    def test_native_version_timeout_still_cleans_disposable_state(self):
        with mock.patch.object(runtime, "native_executable", return_value="synthetic-native.exe"), \
             mock.patch.object(runtime.subprocess, "run", side_effect=runtime.subprocess.TimeoutExpired("synthetic", 10)):
            receipt = runtime.native_version("codex")
        self.assertFalse(receipt["ok"])
        self.assertTrue(receipt["cleanup"]["state_removed"])

    def fake_native(self, root, agent="codex", *, tool_event=False, contamination=False,
                    launch_error=False, timeout=False, export_error=False, output_text=None,
                    metadata_reasoning="high", output_schema=None, returncode=0, interrupt=False, record_out=None):
        source_home, fixture = root / "source-home", root / "fixture"
        for directory in (source_home / ".codex", source_home / ".hermes", source_home / ".agents" / "skills" / "shared", fixture):
            directory.mkdir(parents=True)
        (source_home / ".codex" / "auth.json").write_text(json.dumps({
            "auth_mode": "chatgpt", "tokens": {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh",
            "account_id": "synthetic-account", "extra_secret": "synthetic-excluded"}, "unrelated": "synthetic-excluded"}), encoding="utf-8")
        (source_home / ".hermes" / "auth.json").write_text(json.dumps({"providers": {
            "openai-codex": {"tokens": {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"}},
            "unrelated": {"secret": "synthetic-excluded"}}}), encoding="utf-8")
        (source_home / ".agents" / "skills" / "shared" / "SKILL.md").write_text("shared fixture", encoding="utf-8")
        (source_home / ".codex" / "config.toml").write_text("PERSONAL_SENTINEL", encoding="utf-8")
        source_env = {"HOME": str(source_home), "USERPROFILE": str(source_home), "HERMES_HOME": str(source_home / ".hermes"), "PATH": "synthetic-path",
                      "TAVILY_API_KEY": "synthetic-excluded", "HERMES_PROFILE": "synthetic-excluded",
                      "CODEX_APP_TOOLS_PIPE_PATH": "synthetic-excluded", "OPENAI_BASE_URL": "https://example.invalid"}
        thread_id, session_id = "11111111-1111-1111-1111-111111111111", "20260905_111111_abcdef"
        record = {"probes": [], "launches": [], "exports": [], "auth": []}
        events = [{"type": "thread.started", "thread_id": thread_id}, {"type": "turn.started"}]
        if tool_event:
            events.append({"type": "item.completed", "item": {"id": "tool", "type": "command_execution", "status": "completed"}})
        events += [{"type": "item.completed", "item": {"id": "answer", "type": "agent_message", "text": '{"ok":true}'}},
                   {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}]
        if agent == "codex":
            stdout = "\n".join(json.dumps(item) for item in events)
        else:
            worker = {"ok": not export_error, "output": output_text if output_text is not None else '{"ok":true}',
                      "route_attestation": {"requested": {"model": "test-model", "provider": "openai-codex", "reasoning": "high", "tool_policy": "none"},
                      "observed": {"model": "test-model", "provider": "openai-codex", "reasoning": "high", "tool_calls_count": 0},
                      "ok": not export_error, "errors": ["synthetic worker failure"] if export_error else [],
                      "source": "native-AIAgent-runtime-metadata", "provider_resolved_identity_verified": False},
                      "prompt_isolation": {"verified": True, "canary_absent": True, "native_tool_names": []},
                      "native_result_metadata": {"completed": not export_error, "failed": export_error, "partial": False,
                                                 "interrupted": False, "final_response": output_text if output_text is not None else '{"ok":true}'},
                      "tool_observation": {"source": "native-AIAgent-tool-dispatch-guard", "tool_activity_count": 0,
                                           "execution_blocker_installed": True, "ok": True}}
            stdout = json.dumps(worker)
        stderr = "" if agent == "codex" else f"session_id: {session_id}\n"
        process = mock.Mock(returncode=returncode)
        record["process"] = process
        process.poll.return_value = None if interrupt else 0
        process.communicate.side_effect = [KeyboardInterrupt("synthetic interruption"), (stdout, stderr)] if interrupt else [runtime.subprocess.TimeoutExpired("synthetic", 1), (stdout, stderr)] if timeout else None
        if not timeout and not interrupt:
            process.communicate.return_value = (stdout, stderr)

        def native_run(command, **kwargs):
            env = kwargs["env"]
            if "prompt-input" in command:
                record["probes"].append((command, dict(env)))
                skill = Path(env["CODEX_HOME"]) / "skills" / ".system" / "system" / "SKILL.md"
                skill.parent.mkdir(parents=True, exist_ok=True)
                skill.write_text("system fixture", encoding="utf-8")
                text = "<skills_instructions>leaked" if contamination and len(record["probes"]) == 2 else "native permissions"
                return mock.Mock(returncode=0, stdout=json.dumps([{"role": "developer", "content": [{"text": text}]}]), stderr="")
            record["exports"].append((command, dict(env)))
            row = {"id": session_id, "model": "test-model", "billing_provider": "openai-codex",
                   "model_config": {"reasoning_config": {"effort": "high"}}, "messages": [{"role": "assistant", "content": stdout}]}
            return mock.Mock(returncode=1 if export_error else 0, stdout=json.dumps(row), stderr="synthetic export error" if export_error else "")

        def launch(command, **kwargs):
            env = kwargs["env"]
            record["launches"].append((command, dict(env), kwargs["cwd"]))
            state = Path(env["CODEX_HOME"] if agent == "codex" else env["HERMES_HOME"])
            if agent == "codex":
                record["auth"].append(json.loads((state / "auth.json").read_text(encoding="utf-8")))
            else:
                self.assertFalse((state / "auth.json").exists())
            self.assertFalse(state.is_relative_to(fixture))
            self.assertFalse((state / "config.toml").exists())
            if launch_error:
                raise OSError("synthetic launch failure")
            if agent == "codex":
                Path(command[command.index("-o") + 1]).write_text('{"ok":true}', encoding="utf-8")
                sessions = state / "sessions"
                sessions.mkdir()
                (sessions / f"rollout-{thread_id}.jsonl").write_text("\n".join(json.dumps(item) for item in [
                    {"type": "session_meta", "payload": {"id": thread_id, "model_provider": "openai"}},
                    {"type": "turn_context", "payload": {"model": "test-model", "effort": metadata_reasoning}},
                ]), encoding="utf-8")
            return process

        lifecycle = mock.Mock()
        record["lifecycle"] = lifecycle
        if record_out is not None:
            record_out.update(record)
        with mock.patch.dict(runtime.os.environ, source_env, clear=True), \
             mock.patch.object(Path, "home", return_value=source_home), \
             mock.patch.object(runtime.shutil, "which", return_value="synthetic-launcher"), \
             mock.patch.object(runtime, "native_hermes_runtime", return_value=(Path("synthetic-python"), Path("synthetic-native-source"))), \
             mock.patch.object(runtime.subprocess, "run", side_effect=native_run), \
             mock.patch.object(runtime.subprocess, "Popen", side_effect=launch):
            result = evaluator.run_agent(agent, "synthetic task", fixture, 1, False, "test-model",
                                         "openai-codex", "high", "none", lifecycle, output_schema=output_schema, require_attestation=True)
        lifecycle.register_receipt.assert_not_called()
        record["process"] = process
        return result, record

    def test_unsupported_policy_rejected_before_launch(self):
        for policy, full_tools in (("safe", False), ("full", True), ("none", True)):
            with self.subTest(policy=policy, full_tools=full_tools), \
                 mock.patch.dict(evaluator.os.environ, {}, clear=True), \
                 mock.patch.object(evaluator.shutil, "which", return_value="fake-codex"), \
                 mock.patch.object(Path, "is_file", return_value=False), \
                 mock.patch.object(evaluator.subprocess, "Popen") as launch, \
                 self.assertRaisesRegex(ValueError, "unsupported.*tool"):
                evaluator.run_agent("codex", "task", Path("unused"), 1, full_tools,
                                    "test-model", "openai-codex", "high", policy)
            launch.assert_not_called()

    def test_empty_global_cleanup_does_not_invoke_hermes(self):
        lifecycle = evaluator.HermesSessionLifecycle("missing-hermes", retain=False)
        with mock.patch.object(evaluator.subprocess, "run") as run:
            receipt = lifecycle.cleanup()
        run.assert_not_called()
        self.assertEqual(receipt["created"], [])
        self.assertEqual(receipt["deleted"], [])

    def test_codex_controls_preflight_and_credentials_are_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            result, record = self.fake_native(Path(temp))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["session_ids"], [])
        self.assertEqual(len(record["probes"]), 2)
        command, env, fixture = record["launches"][0]
        for feature in runtime.CODEX_DISABLED_FEATURES:
            self.assertTrue(any(command[index:index + 2] == ["--disable", feature] for index in range(len(command) - 1)))
        for setting in ('model_provider="openai"', "project_doc_max_bytes=0", 'personality="none"',
                        'web_search="disabled"', 'approval_policy="never"'):
            self.assertIn(setting, command)
        self.assertIn("--json", command)
        self.assertIn("--ignore-user-config", command)
        self.assertNotIn("--ephemeral", command)
        self.assertFalse(any(key in env for key in ("TAVILY_API_KEY", "HERMES_PROFILE", "CODEX_APP_TOOLS_PIPE_PATH", "OPENAI_BASE_URL")))
        self.assertNotEqual(Path(env["HOME"]), fixture)
        self.assertFalse(Path(env["CODEX_HOME"]).exists())
        self.assertEqual(result["runtime_contract"]["prompt_isolation"]["disabled_skill_count"], 2)
        self.assertTrue(result["runtime_contract"]["cleanup"]["credentials_removed"])
        self.assertFalse(result["runtime_contract"]["tool_schema_absence_verified"])
        self.assertFalse(result["route_attestation"]["provider_resolved_identity_verified"])
        self.assertEqual(result["route_attestation"]["observed"]["tool_calls_count"], 0)
        self.assertNotIn("synthetic-excluded", json.dumps(record["auth"]))

    def test_contaminated_codex_prompt_never_launches_model(self):
        with tempfile.TemporaryDirectory() as temp:
            result, record = self.fake_native(Path(temp), contamination=True)
        self.assertFalse(result["ok"])
        self.assertEqual(record["launches"], [])
        self.assertTrue(result["runtime_contract"]["cleanup"]["state_removed"])

    def test_codex_tool_event_invalidates_no_tools_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            result, _ = self.fake_native(Path(temp), tool_event=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["runtime_contract"]["tool_observation"]["tool_activity_count"], 1)
        self.assertTrue(any("tool activity" in error for error in result["route_attestation"]["errors"]))
        self.assertEqual(result["output"], '{"ok":true}')

    def test_timeout_and_launch_failure_cleanup_credentials_independently(self):
        for failure in ("timeout", "launch_error"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                result, record = self.fake_native(Path(temp), **{failure: True})
                self.assertFalse(result["ok"])
                self.assertTrue(result["runtime_contract"]["cleanup"]["credentials_removed"])
                self.assertTrue(result["runtime_contract"]["cleanup"]["state_removed"])
                if failure == "timeout":
                    record["process"].kill.assert_called_once()

    def test_hermes_api_worker_uses_memory_credentials_and_disposable_home(self):
        with tempfile.TemporaryDirectory() as temp:
            result, record = self.fake_native(Path(temp), "hermes")
        self.assertTrue(result["ok"], result)
        command, env, _ = record["launches"][0]
        self.assertTrue(command[-1].endswith("evaluation_hermes_worker.py"))
        self.assertEqual(record["exports"], [])
        self.assertEqual(record["auth"], [])
        payload = json.loads(record["process"].communicate.call_args.kwargs["input"])
        self.assertEqual(payload["runtime_home"], env["HERMES_HOME"])
        self.assertNotEqual(payload["credential_owner_home"], payload["runtime_home"])
        self.assertNotIn("synthetic-access", json.dumps(payload))
        self.assertEqual(result["session_ids"], [])
        self.assertEqual(result["runtime_contract"]["controls"]["adapter"], "native-AIAgent-API")
        self.assertTrue(result["runtime_contract"]["controls"]["credentials_in_memory_only"])
        self.assertTrue(result["runtime_contract"]["cleanup"]["credentials_removed"])

    def test_hermes_worker_failure_preserves_answer_and_never_registers_global_session(self):
        with tempfile.TemporaryDirectory() as temp:
            result, _ = self.fake_native(Path(temp), "hermes", export_error=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["output"], '{"ok":true}')
        self.assertEqual(result["session_ids"], [])

    def test_unknown_or_malformed_events_do_not_prove_absence_of_tools(self):
        for text in ('not-json', '{"type":"turn.completed"}', '{"type":"future-tool-event"}'):
            with self.subTest(text=text):
                result = runtime.codex_events(text, evaluator.extract_json)
                self.assertFalse(result["ok"])
                self.assertFalse(result["tool_schema_absence_verified"])

    def test_runtime_preserves_malformed_leading_output(self):
        raw = '\x1b[31mUnexpected text\n{"ok":true}'
        with tempfile.TemporaryDirectory() as temp:
            result, _ = self.fake_native(Path(temp), "hermes", output_text=raw)
        self.assertEqual(result["output"], raw)
        with self.assertRaises(ValueError):
            evaluator.extract_json(result["output"])

    def test_unsupported_provider_rejected_before_auth_or_launch(self):
        with mock.patch.object(runtime, "stage_auth") as auth, \
             mock.patch.object(runtime.subprocess, "Popen") as launch, \
             self.assertRaisesRegex(ValueError, "unsupported evaluator provider"):
            evaluator.run_agent("codex", "task", Path("unused"), 1, False, "test-model", "custom-provider", "high", "none")
        auth.assert_not_called()
        launch.assert_not_called()

    def test_environment_keeps_required_network_settings_and_excludes_synthetic_secrets(self):
        source = {"PATH": "synthetic-path", "HTTPS_PROXY": "https://synthetic-proxy.invalid",
                  "SSL_CERT_FILE": "synthetic-cert.pem", "TAVILY_API_KEY": "synthetic-secret",
                  "UNRELATED_API_KEY": "synthetic-secret", "CODEX_THREAD_ID": "synthetic-parent",
                  "HERMES_SESSION_ID": "synthetic-parent", "HERMES_SYSTEM_PROMPT": "synthetic-override"}
        with tempfile.TemporaryDirectory() as temp:
            env = runtime.runtime_environment(source, Path(temp))
        self.assertEqual(env["HTTPS_PROXY"], source["HTTPS_PROXY"])
        self.assertEqual(env["SSL_CERT_FILE"], source["SSL_CERT_FILE"])
        self.assertFalse(any("synthetic-secret" == value or "synthetic-parent" == value or "synthetic-override" == value for value in env.values()))

    def test_hermes_never_imports_codex_refresh_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_home = root / "source"
            (source_home / ".codex").mkdir(parents=True)
            (source_home / ".codex" / "auth.json").write_text(json.dumps({"tokens": {
                "access_token": "synthetic-codex-access", "refresh_token": "synthetic-codex-refresh"}}), encoding="utf-8")
            source = {"HOME": str(source_home), "HERMES_HOME": str(source_home / ".hermes")}
            env = runtime.runtime_environment(source, root / "runtime")
            with self.assertRaisesRegex(ValueError, "native access-token resolver in memory"):
                runtime.stage_auth("hermes", source, env)
            self.assertFalse((Path(env["HERMES_HOME"]) / "auth.json").exists())

    def test_hermes_worker_checks_endpoint_and_blocks_all_tool_dispatch(self):
        with self.assertRaises(RuntimeError):
            hermes_worker.checked_access_token({"base_url": "https://example.invalid", "api_key": "synthetic-access"})
        self.assertEqual(hermes_worker.checked_access_token({"base_url": hermes_worker.ENDPOINT, "api_key": "synthetic-access"}), "synthetic-access")
        job = {"model": "test-model", "reasoning": "high", "timeout": 1, "prompt": "task", "canary": "CANARY"}
        execution = []
        class Agent:
            model, provider, reasoning_config = "test-model", "openai-codex", {"effort": "high"}
            valid_tool_names = []
            def _execute_tool_calls(self, *_args): execution.append("executed")
            def _execute_tool_calls_sequential(self, *_args): execution.append("executed")
            def _execute_tool_calls_concurrent(self, *_args): execution.append("executed")
            def run_conversation(self, _prompt):
                self._execute_tool_calls(None)
                return {"completed": True, "final_response": "answer"}
        factory = mock.Mock(return_value=Agent())
        result = hermes_worker.execute_agent(job, "synthetic-access", factory, lambda _agent: "native prompt")
        self.assertFalse(result["ok"])
        self.assertEqual(result["failure"]["kind"], "tool")
        self.assertEqual(execution, [])
        self.assertTrue(factory.call_args.kwargs["skip_memory"])
        self.assertTrue(factory.call_args.kwargs["skip_context_files"])
        self.assertFalse(factory.call_args.kwargs["load_soul_identity"])

    def test_hermes_worker_rejects_context_canary_before_model_call(self):
        agent = mock.Mock(valid_tool_names=[])
        job = {"model": "test-model", "reasoning": "high", "timeout": 1, "prompt": "task", "canary": "CANARY"}
        with self.assertRaisesRegex(RuntimeError, "prompt/tool isolation failed"):
            hermes_worker.execute_agent(job, "synthetic-access", lambda **_kwargs: agent, lambda _agent: "CANARY")
        agent.run_conversation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
