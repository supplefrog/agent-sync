"""Fresh Hermes API child: native credentials stay in memory, tools cannot run."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import math
import os
import sys
import re
import time
import threading
import subprocess
from pathlib import Path
from typing import Any, Callable
from evaluation_runtime import native_transport_failure, require_no_install_environment

ENDPOINT = "https://chatgpt.com/backend-api/codex"
CONTEXT_MARKERS = ("<available_skills>", "<skills_instructions>", "MEMORY_SUMMARY",
                   "[INSTRUCTION-AUTHORING]", "[RECONCILIATION]")


def checked_access_token(credentials: dict) -> str:
    if credentials.get("base_url") != ENDPOINT or not isinstance(credentials.get("api_key"), str) or not credentials["api_key"]:
        raise RuntimeError("native Hermes credential endpoint or access token is unsupported")
    return credentials["api_key"]


NO_TOOL_AGENT_CONFIG = {"environment_probe": False, "api_max_retries": 1,
                        "auto_recovery_cycles": 0, "intent_ack_continuation": False,
                        "empty_response_guard": {"enabled": False}}
NO_INSTALL_LSP_CONFIG = {"enabled": False, "install_strategy": "off"}


def prepare_no_tool_config(runtime_home: str) -> None:
    """Use supported native config keys only in the already-owned disposable home."""
    require_no_install_environment(os.environ)
    destination = Path(runtime_home) / "config.yaml"
    with destination.open("x", encoding="utf-8") as stream:
        json.dump({"agent": NO_TOOL_AGENT_CONFIG, "lsp": NO_INSTALL_LSP_CONFIG}, stream)


def prepare_study_config(runtime_home: str, *, direct_backend: bool = False) -> None:
    require_no_install_environment(os.environ)
    with (Path(runtime_home)/'config.yaml').open('x',encoding='utf-8') as stream:
        config = {'lsp':NO_INSTALL_LSP_CONFIG}
        if direct_backend: config['agent'] = {'environment_probe': False}
        json.dump(config,stream)


def verify_no_install_config(config: dict) -> None:
    lsp=config.get('lsp',{})
    if any(type(lsp.get(k)) is not type(v) or lsp.get(k)!=v for k,v in NO_INSTALL_LSP_CONFIG.items()):
        raise RuntimeError('native per-run LSP no-install control unsupported or ineffective')


def verify_no_tool_config(config: dict) -> None:
    agent = config.get("agent", {})
    for key, expected in NO_TOOL_AGENT_CONFIG.items():
        actual = agent.get(key)
        pairs = [(actual, expected)]
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                raise RuntimeError("native per-run no-tool config is unsupported or ineffective")
            pairs = [(actual.get(nested), value) for nested, value in expected.items()]
        if any(type(value) is not type(wanted) or value != wanted for value, wanted in pairs):
            raise RuntimeError("native per-run no-tool config is unsupported or ineffective")


def observed_no_tool_controls(agent) -> dict:
    expected = {"_environment_probe": False, "_api_max_retries": 1,
                "_auto_recovery_cycles": 0, "_intent_ack_continuation": False,
                "_empty_guard_enabled": False}
    observed = {key: getattr(agent, key, None) for key in expected}
    if any(type(observed[key]) is not type(value) or observed[key] != value
           for key, value in expected.items()):
        raise RuntimeError("native agent did not apply the per-run no-tool controls")
    return observed


def native_usage(native: dict, agent) -> dict:
    """Preserve canonical counters without adding overlapping token buckets.

    Session aggregates cannot prove coverage of failed requests or auxiliary
    models. A last-response usage record only establishes single-response
    coverage when the native completed-response counter is exactly one.
    """
    keys = ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens',
            'reasoning_tokens', 'prompt_tokens', 'completion_tokens', 'total_tokens')
    def counter(key):
        value = native.get(key, getattr(agent, 'session_' + key, None))
        return value if type(value) is int and value >= 0 else None
    tokens = {key: counter(key) for key in keys}
    calls = counter('api_calls')
    session_calls = getattr(agent, 'session_api_calls', None)
    if type(session_calls) is not int or session_calls < 0:
        session_calls = None
    last = getattr(agent, '_last_turn_usage', None)
    last_observed = isinstance(last, dict) and all(type(last.get(k)) is int and last[k] >= 0
                                                  for k in ('input_tokens', 'output_tokens'))
    with_usage = 1 if calls == session_calls == 1 and last_observed else 0 if calls == session_calls == 0 else None
    without_usage = 0 if with_usage is not None else None
    estimate = native.get('estimated_cost_usd', getattr(agent, 'session_estimated_cost_usd', None))
    if type(estimate) not in (int, float) or not math.isfinite(estimate) or estimate < 0:
        estimate = None
    status = native.get('cost_status', getattr(agent, 'session_cost_status', None))
    source = native.get('cost_source', getattr(agent, 'session_cost_source', None))
    return {'source': 'native-Hermes-canonical-session-counters', 'tokens': tokens,
            'api_calls': calls,
            'cost': {'estimated_cost_usd': estimate, 'billed_cost_usd': None,
                     'status': status if isinstance(status, str) and status in {'known', 'unknown', 'estimated', 'included', 'unpriced'} else None,
                     'source': source if isinstance(source, str) and source in {'none', 'official_docs_snapshot', 'provider_models_api', 'models.dev', 'unknown'} else None},
            'coverage': {'scope': 'main-agent completed responses; not physical attempts or whole system',
                         'aggregate_fields_present': all(value is not None for value in tokens.values()),
                         'session_completed_responses': session_calls,
                         'completed_responses_with_usage': with_usage,
                         'completed_responses_without_usage': without_usage,
                         'completed_response_usage_complete': with_usage is not None and all(value is not None for value in tokens.values()),
                         'failed_attempt_coverage': 'unknown', 'auxiliary_coverage': 'unverified',
                         'complete_for_system_efficiency': False}}


def execute_agent(job: dict, access_token: str, factory: Callable, build_prompt: Callable) -> dict:
    """The native registry is empty and all native tool-dispatch paths are blocked."""
    agent = factory(
        model=job["model"], provider="openai-codex", api_mode="codex_responses",
        api_key=access_token, base_url=ENDPOINT, enabled_toolsets=["none"],
        skip_context_files=True, load_soul_identity=False, skip_memory=True,
        skip_background_review=True, quiet_mode=True, save_trajectories=False,
        max_iterations=1, run_budget_seconds=job["timeout"],
        reasoning_config={"enabled": True, "effort": job["reasoning"]}, fallback_model=None,
    )
    attempts = 0

    def reject_tool_execution(*_args: Any, **_kwargs: Any) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("tool execution is prohibited in the evaluator")

    for method in ("_execute_tool_calls", "_execute_tool_calls_sequential", "_execute_tool_calls_concurrent"):
        if not callable(getattr(agent, method, None)):
            raise RuntimeError("native Hermes tool-dispatch boundary is unavailable")
        setattr(agent, method, reject_tool_execution)
    assembled = build_prompt(agent)
    markers = [*CONTEXT_MARKERS, job["canary"]]
    if agent.valid_tool_names or any(marker in assembled for marker in markers) or access_token in assembled:
        raise RuntimeError("native Hermes prompt/tool isolation failed")
    native_controls = observed_no_tool_controls(agent)
    prompt = job["prompt"]
    if job.get("output_schema") is not None:
        prompt += "\n\nReturn only one JSON object matching this schema:\n" + json.dumps(job["output_schema"])
    transport_failure = None
    try:
        native = agent.run_conversation(prompt)
    except Exception as exc:
        transport_failure = native_transport_failure({"status_code": getattr(exc, "status_code", None), "code": getattr(exc, "code", None)})
        native = {"completed": False, "failed": True, "final_response": ""}
    output = native.get("final_response", "")
    if not isinstance(output, str) or access_token in output:
        raise RuntimeError("native Hermes output failed the secret boundary")
    observed = {"model": agent.model, "provider": agent.provider,
                "reasoning": getattr(agent, "reasoning_config", {}).get("effort"), "tool_calls_count": attempts}
    expected = {"model": job["model"], "provider": "openai-codex", "reasoning": job["reasoning"]}
    errors = [f"native {key} metadata missing or mismatched" for key in expected if observed[key] != expected[key]]
    if attempts:
        errors.append("native Hermes attempted prohibited tool execution")
    if not native.get("completed") or any(native.get(key) for key in ("failed", "interrupted", "partial")):
        errors.append("native Hermes conversation did not complete")
        transport_failure = transport_failure or native_transport_failure({
            "http_status": native.get("http_status"), "code": native.get("error_code"),
            "error": native.get("error") if isinstance(native.get("error"), dict) else {},
        })
    failure = None
    if errors:
        failure = ({"kind": "tool", "source": "runtime-control", "code": "prohibited-native-tool-activity"} if attempts
                   else {"kind": "route", "source": "runtime-control", "code": "native-route-mismatch"}
                   if any("metadata" in error for error in errors)
                   else transport_failure)
    return {
        "ok": not errors, "output": output, "failure": failure,
        "native_controls": native_controls,
        "native_usage": native_usage(native, agent),
        "route_attestation": {
            "requested": {**expected, "tool_policy": "none"}, "observed": observed,
            "ok": not errors, "errors": errors, "source": "native-AIAgent-runtime-metadata",
            "provider_resolved_identity_verified": False,
        },
        "prompt_isolation": {
            "verified": True, "source": "native-AIAgent-build-system-prompt",
            "sha256": hashlib.sha256(assembled.encode("utf-8")).hexdigest(), "assembled_prompt": assembled,
            "canary": job["canary"], "canary_absent": job["canary"] not in assembled,
            "contamination": [], "native_tool_names": list(agent.valid_tool_names),
            "tool_schema_absence_verified": False,
        },
        "tool_observation": {"source": "native-AIAgent-tool-dispatch-guard", "tool_activity_count": attempts,
                             "execution_blocker_installed": True, "ok": attempts == 0,
                             "tool_schema_absence_verified": False},
        "native_result_metadata": {**{key: native.get(key) for key in
                                   ("completed", "failed", "interrupted", "partial", "model", "provider", "api_calls")},
                                   "final_response": output},
    }


def study_guard(tool_name, args, fixture, catalog_root):
    """Conservative native request gate, not an operating-system sandbox."""
    def contained(value, root):
        path = Path(value)
        path = path if path.is_absolute() else fixture / path
        return path.resolve().is_relative_to(root.resolve())
    if tool_name in ("skills_list", "skill_view"):
        return None
    if tool_name in ("read_file", "search_files", "write_file", "patch"):
        paths = [args.get("path", ".")]
        if tool_name == "patch" and args.get("mode") == "patch":
            paths = re.findall(r"(?m)^\*\*\* (?:(?:Update|Add|Delete) File|Move to): (.+)$", args.get("patch", ""))
            if not paths:
                return "Patch paths must be explicit"
        if all(isinstance(p, str) and (contained(p, fixture) or tool_name == "read_file" and contained(p, catalog_root)) for p in paths):
            return None
        return "Paths outside the study fixture are prohibited"
    if tool_name == "terminal":
        if any(args.get(key) for key in ("background", "persist_on_release", "pty")):
            return "Persistent or background terminal jobs are prohibited"
        if args.get("workdir") and not contained(args["workdir"], fixture):
            return "Terminal working directory must be in the fixture"
        command = args.get("command", "")
        # Allow fixture testing/listing, reject shell composition, arbitrary code,
        # install/network programs and absolute/parent paths.
        if (isinstance(command, str) and not re.search(r"[;&|<>`\r\n]|\$|\.\.|https?:|[A-Za-z]:|(?:^|\s)/", command)
                and re.fullmatch(r"(?:python(?:\.exe)? -m (?:pytest|unittest)(?: [A-Za-z0-9_. /=-]+)?|pytest(?: [A-Za-z0-9_. /=-]+)?|(?:pwd|ls|dir)(?: [A-Za-z0-9_. /=-]+)?)", command)):
            return None
        return "Only simple fixture test/listing commands are permitted"
    return "This native study prohibits management, delegation and external tools"


TERMINAL_CONTRACT = ('Fixture terminal boundary: only simple fixture test/listing commands are supported: '
    'python -m unittest [options], python -m pytest [options], pytest [options], pwd, ls or dir. '
    'No shell composition, cd prefixes, absolute paths, scripts, network/install or background commands. '
    'Use the fixture as the working directory. File tools provide source inspection and editing.')


def advertise_study_terminal(agent):
    tools = copy.deepcopy(agent.tools)
    found = False
    for tool in tools:
        function = tool.get('function', {})
        if function.get('name') == 'terminal':
            function['description'] = TERMINAL_CONTRACT + '\n\n' + function.get('description', '')
            found = True
    if not found: raise RuntimeError('Native terminal schema unavailable')
    agent.tools = tools


def direct_python_terminal(args, fixture, timeout):
    """Study-only argv backend, after the unchanged tool-dispatch guard."""
    fixture = Path(fixture).resolve()
    message = study_guard('terminal', args, fixture, fixture/'unused-catalog')
    if message:
        return json.dumps({'error': message, 'success': False})
    workdir = Path(args.get('workdir') or fixture)
    workdir = (workdir if workdir.is_absolute() else fixture/workdir).resolve()
    if not workdir.is_dir():
        return json.dumps({'error': 'Fixture working directory unavailable', 'success': False})
    command = args['command'].split()
    if command[0] in ('pwd', 'ls', 'dir'):
        paths = [p for p in command[1:] if not p.startswith('-')]
        if command[0] == 'pwd' and command[1:] or len(paths) > 1:
            return json.dumps({'error': 'Unsupported fixture listing', 'success': False})
        target = (workdir / (paths[0] if paths else '.')).resolve()
        if not target.is_relative_to(fixture):
            return json.dumps({'error': 'Listing outside fixture', 'success': False})
        output = str(workdir) if command[0] == 'pwd' else '\n'.join(p.name for p in sorted(target.iterdir()))
        return json.dumps({'output': output, 'exit_code': 0, 'success': True, 'backend': 'direct-python-argv'})
    if command[0] in ('python', 'python.exe'):
        argv = [sys.executable, '-B', *command[1:]]
    elif command[0] == 'pytest':
        argv = [sys.executable, '-B', '-m', 'pytest', *command[1:]]
    else:
        return json.dumps({'error': 'Unsupported direct test command', 'success': False})
    if any(part.split('=')[-1].startswith(('/', '\\')) for part in command[1:]):
        return json.dumps({'error': 'Absolute test option path', 'success': False})
    limit = args.get('timeout', timeout)
    if type(limit) not in (int, float) or not 0 < limit <= timeout:
        return json.dumps({'error': 'Invalid bounded timeout', 'success': False})
    env = {k:v for k,v in os.environ.items() if k.upper() in
           ('SYSTEMROOT','WINDIR','PATH','PATHEXT','SYSTEMDRIVE','TEMP','TMP')}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    try:
        result = subprocess.run(argv, cwd=workdir, env=env, shell=False, text=True,
                                capture_output=True, timeout=limit, encoding='utf-8', errors='replace')
        return json.dumps({'output': result.stdout + result.stderr, 'exit_code': result.returncode,
                           'success': result.returncode == 0, 'backend': 'direct-python-argv'})
    except subprocess.TimeoutExpired:
        return json.dumps({'error': 'Fixture test timeout', 'success': False, 'backend': 'direct-python-argv'})


def bounded_terminal_schema(native_schema, timeout):
    """Advertise the same command bound enforced by the disposable handler."""
    if type(timeout) is not int or timeout < 1:
        raise ValueError('Terminal schema needs a positive whole-second bound')
    schema = copy.deepcopy(native_schema)
    parameter = schema['parameters']['properties']['timeout']
    parameter.update(default=timeout, maximum=timeout, minimum=1,
        description=f'Maximum requested command seconds (default {timeout}; maximum {timeout}). '
                    'Foreground only; execution can return earlier under existing runtime limits.')
    schema['description'] = TERMINAL_CONTRACT + '\nExecution backend: direct Python argv; no Bash or shell interpretation.'
    return schema


def install_direct_terminal(job):
    """Use the supported registry API only in this disposable worker process."""
    from tools import terminal_tool as native_terminal
    from tools.registry import registry
    def handler(args, **kwargs):
        started = time.monotonic()
        message = study_guard('terminal', args, Path(job['fixture']), Path(job['fixture'])/'unused-catalog')
        if message: return json.dumps({'error':message,'success':False})
        requested_timeout = args.get('timeout', job['timeout'])
        if type(requested_timeout) not in (int,float) or not 0 < requested_timeout <= job['timeout']:
            return json.dumps({'error':'Invalid bounded timeout','success':False})
        # Preserve the original native scope, prepared-argument, lifecycle,
        # workdir/self-repo and approval floors; never use force=True.
        try:
            from tools.terminal_scope import enforce_no_refusal
            from agent.terminal_approval_batch import validate_prepared_terminal
            from agent.deadline import run_bounded_sync
            enforce_no_refusal()
            validate_prepared_terminal(args)
            def guards():
                config = native_terminal._get_env_config()
                if config['env_type'] != 'local': raise RuntimeError('Direct backend requires local native terminal scope')
                native_terminal._pre_exec_block(args['command'], env=None, env_type='local',
                    cwd=job['fixture'], workdir=args.get('workdir'), session_key=kwargs.get('session_id') or '')
                native_terminal._run_approval_guards(args['command'], 'local', config, force=False)
            bounded = run_bounded_sync(guards, job['timeout'], label='study.direct-terminal-native-guards')
            if bounded.timed_out: return json.dumps({'error':'Native terminal guard timeout','success':False})
        except native_terminal._Rejected as exc:
            return exc.result_json
        except Exception as exc:
            return json.dumps({'error':'Native terminal guard unavailable or refused','error_type':type(exc).__name__,'success':False})
        remaining = job['timeout'] - (time.monotonic() - started)
        if remaining <= 0: return json.dumps({'error':'Native terminal deadline expired','success':False})
        return direct_python_terminal({**args,'timeout':min(requested_timeout,remaining)}, job['fixture'], job['timeout'])
    schema = bounded_terminal_schema(native_terminal.TERMINAL_SCHEMA, job['timeout'])
    registry.register(name='terminal', toolset='terminal', schema=schema, handler=handler,
        check_fn=lambda: Path(sys.executable).is_file(), override=True, max_result_size_chars=100_000)
    def verify():
        if registry.get_entry('terminal').handler is not handler:
            raise RuntimeError('Task-local terminal registration ineffective')
    verify()
    return ({'name': 'direct-python-argv', 'registration_verified': True,
             'registry_source_sha256': hashlib.sha256(Path(sys.modules['tools.registry'].__file__).read_bytes()).hexdigest()}, verify)


def rejection_shape(tool, args):
    """Safe causal diagnostics: categories and digest, no raw command text."""
    if tool != 'terminal': return {'code': 'nonterminal-boundary'}
    command = args.get('command', '')
    command = command if isinstance(command, str) else ''
    return {'command_sha256': hashlib.sha256(command.encode()).hexdigest(),
            'shell_composition': bool(re.search(r'[;&|<>`\r\n]|\$', command)),
            'absolute_or_parent_path': bool(re.search(r'\.\.|[A-Za-z]:|(?:^|\s)/', command)),
            'cd_prefix': bool(re.match(r'\s*cd\s', command)),
            'persistent_requested': any(bool(args.get(key)) for key in ('background','persist_on_release','pty'))}


def study_tool_event(call_id, name, args, parsed, fixture, catalog_root):
    """Bounded action evidence, never raw output or arbitrary tool arguments."""
    parsed = parsed if isinstance(parsed, dict) else {}
    exit_code = parsed.get('exit_code')
    exit_code = exit_code if type(exit_code) is int else None
    event = {'type': 'native-tool-completed', 'tool': name, 'call_id': call_id,
             'success': not parsed.get('error') and parsed.get('success', True) is not False and (exit_code is None or exit_code == 0),
             'exit_code': exit_code}
    path = args.get('path')
    if isinstance(path, str):
        path = Path(path) if Path(path).is_absolute() else fixture / path
        resolved = path.resolve()
        if resolved.is_relative_to(fixture): event['fixture_path'] = resolved.relative_to(fixture).as_posix()
        elif resolved.is_relative_to(catalog_root): event['catalog_path'] = resolved.relative_to(catalog_root).as_posix()
    if name == 'terminal' and study_guard(name, args, fixture, catalog_root) is None:
        event['command'] = args.get('command')
        if parsed.get('backend') == 'direct-python-argv': event['execution_backend'] = parsed['backend']
    return event


def run_with_deadline(agent, prompt, timeout):
    """Stop this owned native turn; leave receipt/owner-thread cleanup time.

    Native run_budget_seconds is a wrap-up hint, not a hard wall. Use the
    installed cross-thread interrupt and transport-shutdown seams; never close
    a live OpenSSL client from the timer thread. The outer watchdog remains.
    """
    interrupt = getattr(agent, 'interrupt', None)
    drain = getattr(agent, '_drain_transports_after_abandonment', None)
    if not callable(interrupt) or not callable(drain):
        raise RuntimeError('Native bounded interruption seams unavailable')
    fired = threading.Event()
    errors = []
    def expire():
        fired.set()
        try:
            interrupt(hard_cancel=True, tool_reason='batch_deadline')
        except Exception as exc:
            errors.append('interrupt-' + type(exc).__name__)
        try:
            drain(reason='evaluation_turn_deadline')
        except Exception as exc:
            errors.append('transport-shutdown-' + type(exc).__name__)
    timer = threading.Timer(timeout, expire)
    timer.name = 'evaluation-native-deadline'
    timer.daemon = True
    timer.start()
    try:
        native = agent.run_conversation(prompt)
    finally:
        timer.cancel()
        timer.join(timeout=5)
        if timer.is_alive():
            raise RuntimeError('Native deadline callback did not settle; cleanup uncertain')
    if fired.is_set():
        native = {**native, 'completed': False, 'interrupted': True}
    return native, {'seconds': timeout, 'fired': fired.is_set(), 'errors': errors,
                    'timer_settled': True, 'source': 'native-interrupt-and-socket-shutdown'}


def execute_skill_study(job, access_token, factory, build_prompt):
    from artifact_hash import freeze_candidate
    from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
    from tools.skills_tool import skills_list
    fixture = Path(job["fixture"]).resolve()
    catalog_root = Path(job["runtime_home"]) / "skills"
    agent = None
    leases, events, reads = [], [], []
    blocked = []
    names = []
    for item in job["catalog"]:
        text = Path(item["path"]).read_text(encoding="utf-8")
        match = re.search(r"(?m)^name:\s*(.+)$", text)
        names.append(match.group(1).strip().strip("\"'") if match else Path(item["path"]).parent.name)
    def gate(tool_name, args, **kwargs):
        message = study_guard(tool_name, args, fixture, catalog_root)
        if message:
            blocked.append({"tool": tool_name, "reason": message, 'shape': rejection_shape(tool_name, args)})
            return {"action": "block", "message": message + (' ' + TERMINAL_CONTRACT if tool_name == 'terminal' else '')}
    def completed(call_id, name, args, raw):
        parsed = raw if isinstance(raw, dict) else None
        if parsed is None:
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                parsed = {}
        parsed = parsed if isinstance(parsed, dict) else {}
        events.append(study_tool_event(call_id, name, args, parsed, fixture, catalog_root))
        if name == "skill_view" and parsed.get("success") and not args.get("file_path"):
            path = Path(parsed.get("_source_path", ""))
            for item in job["catalog"]:
                if path.name == "SKILL.md" and path.parent.name == Path(item["path"]).parent.name and path.is_file():
                    frozen = freeze_candidate(path)
                    if frozen["package_sha256"] == item["package_sha256"]:
                        reads.append({**item, "source": "successful-native-skill_view", "native_source_path": str(path)})
    try:
        manager = get_plugin_manager()
        context = PluginContext(PluginManifest(name="study-runtime-guard"), manager)
        leases.append(context.register_hook("pre_tool_call", gate))
        agent = factory(model=job["model"], provider="openai-codex", api_mode="codex_responses",
            api_key=access_token or "assembly-probe-no-credential", base_url=ENDPOINT,
            enabled_toolsets=["terminal", "file", "skills"], skip_context_files=True,
            load_soul_identity=False, skip_memory=True, skip_background_review=True,
            quiet_mode=True, save_trajectories=False, max_iterations=job["max_iterations"],
            run_budget_seconds=job["timeout"], reasoning_config={"enabled": True, "effort": job["reasoning"]},
            fallback_model=None, tool_complete_callback=completed)
        advertise_study_terminal(agent)
        assembled = build_prompt(agent)
        actual = sorted(s["name"] for s in json.loads(skills_list()).get("skills", []))
        if actual != sorted(names) or len(actual) != len(set(actual)) or any(name not in assembled for name in names):
            raise RuntimeError("Native catalog differs from the declared exact catalog")
        if access_token and access_token in assembled or any(marker in assembled for marker in CONTEXT_MARKERS[1:]):
            raise RuntimeError("Native study prompt contamination")
        metadata = {"model": agent.model, "provider": agent.provider,
                    "reasoning": agent.reasoning_config.get("effort")}
        if metadata != {"model": job["model"], "provider": "openai-codex", "reasoning": job["reasoning"]}:
            raise RuntimeError("Native study route mismatch")
        before = time.monotonic()
        if job.get("assembly_only"):
            native, deadline = {"completed": True, "api_calls": 0}, {'assembly_only': True}
        else:
            native, deadline = run_with_deadline(agent, job["prompt"], job["timeout"])
        result = {"ok": bool(native.get("completed") and not any(native.get(k) for k in ("failed", "partial", "interrupted"))),
            "assembly_only": bool(job.get("assembly_only")), "model_launched": not job.get("assembly_only"),
            "requested_route": {"model": job["model"], "provider": "openai-codex", "reasoning": job["reasoning"]},
            "agent_observed_route": metadata, "provider_resolved_identity_verified": False,
            "catalog_evidence": {"declared_names": sorted(names), "native_catalog_names": actual,
                                 "exact_catalog_verified": True, "prompt_sha256": hashlib.sha256(assembled.encode()).hexdigest()},
            "skill_read_evidence": reads, "events": events, "blocked_requests": blocked,
            "final_response": native.get('final_response'),
            "tokens": {"input": getattr(agent, "session_input_tokens", None), "output": getattr(agent, "session_output_tokens", None)},
            "api_calls": native.get("api_calls"), "native_usage": native_usage(native, agent),
            "turn_deadline": deadline,
            "dollars": None, "cost_status": "subscription-dollars-unavailable",
            "native_seconds": time.monotonic() - before,
            "limits": ["native request gate is not operating-system isolation", "fixture tests execute model-edited code"]}
        if access_token and access_token in json.dumps(result):
            raise RuntimeError("Credential output rejected")
        return result
    finally:
        if agent is not None:
            agent.close()
        for lease in reversed(leases):
            lease.dispose()


def finalize_usage_receipt(receipt, observer, leases, canary_file):
    """Cleanup failure cannot erase observed usage or the sanitized receipt."""
    receipt.setdefault('native_usage', {})['lifecycle'] = observer.snapshot()
    if observer.recording is not None:
        receipt['request_recording'] = observer.finish_recording()
        if receipt.get('model_launched') is True and not receipt['request_recording']['complete']:
            receipt['ok'] = False
            receipt['failure'] = {'kind': 'recording', 'source': 'runtime-control',
                                  'code': 'request-recording-incomplete'}
    usage = receipt['native_usage']
    ledger = usage['lifecycle']
    posts = [event for event in ledger['events'] if event['hook'] == 'post_api_request']
    coverage = usage.get('coverage', {})
    calls = usage.get('api_calls')
    if (type(calls) is int and calls >= 0 and coverage.get('session_completed_responses') == calls
            and len(posts) == calls and ledger['dropped_events'] == 0):
        with_usage = sum(event['usage_present'] and all(type(event['tokens'][key]) is int and event['tokens'][key] >= 0
                                                      for key in ('input_tokens', 'output_tokens')) for event in posts)
        coverage.update(completed_responses_with_usage=with_usage, completed_responses_without_usage=calls-with_usage,
                        completed_response_usage_complete=with_usage == calls and coverage.get('aggregate_fields_present') is True,
                        completed_usage_coverage_source='native-post_api_request matched native completed-response count')
    errors = observer.close()
    from evaluation_usage import reconcile_program_usage
    proof = reconcile_program_usage(usage)
    usage['accounting_reconciliation'] = proof
    if receipt.get('catalog_evidence', {}).get('exact_catalog_verified') is True and receipt.get('model_launched') is True and proof['verified']:
        coverage.update(whole_system_complete=True, scope=proof['scope'], auxiliary_coverage='observed-zero-central-dispatches',
                        complete_for_system_efficiency=True)
        usage['provider_physical_attempt_count'] = proof['physical_attempt_count']
        receipt['host_version'] = 'Hermes-accounting-source-' + hashlib.sha256(json.dumps(ledger['native_sources_before'],sort_keys=True).encode()).hexdigest()
    for lease in reversed(leases):
        try:
            lease.dispose()
        except Exception as exc:
            errors.append('usage-hook-cleanup-' + type(exc).__name__)
    if canary_file is not None:
        try:
            canary_file.unlink(missing_ok=True)
        except Exception as exc:
            errors.append('canary-cleanup-' + type(exc).__name__)
    receipt['worker_cleanup_errors'] = errors
    if errors:
        receipt['ok'] = False
        receipt['failure'] = {'kind': 'cleanup', 'source': 'runtime-control', 'code': 'worker-cleanup-failed'}
        if 'route_attestation' in receipt:
            receipt['route_attestation']['ok'] = False
            receipt['route_attestation']['errors'].append('worker cleanup failed')


def main() -> int:
    diagnostics = io.StringIO()
    canary_file = None
    from evaluation_usage import NativeUsageObserver, HOOKS
    usage_observer = NativeUsageObserver()
    usage_leases = []
    try:
        job = json.loads(sys.stdin.read())
        require_no_install_environment(os.environ)
        with contextlib.redirect_stdout(diagnostics), contextlib.redirect_stderr(diagnostics):
            sys.path.insert(0, job["native_source"])
            # Resolve only Hermes' own selected provider before changing homes.
            # CODEX_HOME already points at empty disposable state, so the native
            # resolver cannot import credentials from the user's Codex account.
            os.environ["HERMES_HOME"] = job["credential_owner_home"]
            from hermes_cli.auth_codex import resolve_codex_runtime_credentials
            if job.get("assembly_only"):
                access_token = None
            else:
                credentials = resolve_codex_runtime_credentials(refresh_if_expiring=False)
                access_token = checked_access_token(credentials)
                credentials.clear()
            if job.get('request_recording'):
                recording = job['request_recording']
                usage_observer.enable_recording(recording['directory'], recording['binding'], forbidden=(access_token,))
            os.environ["HERMES_HOME"] = job["runtime_home"]
            os.environ["TERMINAL_CWD"] = job["fixture"]
            from hermes_constants import set_hermes_home_override
            set_hermes_home_override(job["runtime_home"])
            os.chdir(job["fixture"])
            canary = "EVALUATOR_CONTEXT_CANARY_" + hashlib.sha256(os.urandom(32)).hexdigest()
            job["canary"] = canary
            (Path(job["runtime_home"]) / "SOUL.md").write_text(canary, encoding="utf-8")
            candidate = Path(job["fixture"]) / "AGENTS.md"
            if not candidate.exists():
                with candidate.open("x", encoding="utf-8") as stream:
                    stream.write(canary)
                canary_file = candidate
            if job.get("purpose") != "native-skill-study":
                prepare_no_tool_config(job["runtime_home"])
                from hermes_cli.config import load_config_readonly
                verify_no_tool_config(load_config_readonly())
            else:
                prepare_study_config(job['runtime_home'], direct_backend=job.get('terminal_backend') == 'direct-python-argv')
            from hermes_cli.config import load_config_readonly
            verify_no_install_config(load_config_readonly())
            backend = None
            if job.get('terminal_backend'):
                if job['terminal_backend'] != 'direct-python-argv':
                    raise ValueError('Unsupported native study terminal backend')
                if load_config_readonly().get('agent', {}).get('environment_probe') is not False:
                    raise RuntimeError('Direct backend must not start the Bash environment probe')
                backend, verify_backend = install_direct_terminal(job)
            from run_agent import AIAgent
            from agent.system_prompt import build_system_prompt
            from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager, VALID_HOOKS
            if not set(HOOKS) <= set(VALID_HOOKS):
                raise RuntimeError('native usage lifecycle hooks unavailable')
            usage_context = PluginContext(PluginManifest(name='evaluation-usage-observer'), get_plugin_manager())
            for name in HOOKS:
                usage_leases.append(usage_context.register_hook(name, usage_observer.callback(name)))
            usage_observer.watch_auxiliary_dispatches()
            for item in job.get('catalog', []):
                body = Path(item['path']).read_text(encoding='utf-8').split('---', 2)[-1].strip()
                if body: usage_observer.body_probes.append(body)
            if '<optional-instruction-exposure>\n' in job.get('prompt', ''):
                body = job['prompt'].split('<optional-instruction-exposure>\n', 1)[1].split('\n</optional-instruction-exposure>', 1)[0]
                usage_observer.body_probes.append(body)
            def observed_factory(*args, **kwargs):
                agent = AIAgent(*args, **kwargs)
                if not all(callable(getattr(agent, name, None)) for name in
                           ('interrupt', '_drain_transports_after_abandonment')):
                    raise RuntimeError('Native deadline support unavailable before dispatch')
                if backend: verify_backend()
                if backend and getattr(agent, '_environment_probe', True) is not False:
                    raise RuntimeError('Native agent ignored the direct backend no-Bash probe control')
                usage_observer.watch_request_clients(agent)
                return agent
            def recorded_prompt(agent):
                assembled = build_system_prompt(agent)
                usage_observer.record_prompts(assembled, job['prompt'])
                return assembled
            receipt = (execute_skill_study(job, access_token, observed_factory, recorded_prompt)
                       if job.get("purpose") == "native-skill-study"
                       else execute_agent(job, access_token, observed_factory, recorded_prompt))
            receipt['runtime_controls']={'lsp':dict(NO_INSTALL_LSP_CONFIG),'native_config_readback_verified':True}
            if backend:
                verify_backend()
                receipt['terminal_backend'] = backend
            del access_token
        receipt["suppressed_native_diagnostic_characters"] = len(diagnostics.getvalue())
    except BaseException as exc:
        import traceback
        # Native errors or diagnostic buffers can include credentials; never
        # propagate their text, argv, environment, or traceback to the report.
        receipt = {"ok": False, "error_type": type(exc).__name__,
                   "error_locations": [{"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                                       for frame in traceback.extract_tb(exc.__traceback__)],
                   "error": "native Hermes worker could not complete the isolated call",
                   "failure": {"kind": "isolation", "source": "runtime-control", "code": type(exc).__name__}}
    finally:
        finalize_usage_receipt(receipt, usage_observer, usage_leases, canary_file)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
