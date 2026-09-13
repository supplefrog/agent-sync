"""Isolated artifact trial using the existing V3 router and native leaf lifecycle.

Not an admission gate or alternate router. Only a replayed model decision may
launch; every trial still requires an external parent-owned artifact check.
"""
from __future__ import annotations
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
from evaluation_hermes_worker import checked_access_token


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require_model(pin):
    if pin['dispatch']['kind'] != 'model' or pin['decision']['outcome'] != 'selected_model':
        raise ValueError('Non-model route decision: no worker may launch')
    if pin['dispatch']['route'] != pin['decision']['route']:
        raise ValueError('Dispatch changed the selected route')
    return pin['decision']


def main():
    job = json.loads(sys.stdin.read())
    output = Path(job['output']).resolve()
    fixture = Path(job['fixture']).resolve()
    if output.is_relative_to(fixture):
        raise ValueError('Controller output must be outside the model fixture')
    result = {'ok': False, 'model_launched': False, 'lane': 'routed-artifact-pilot-v1',
              'quality_admission': False, 'provider_resolved_identity_verified': False}
    diagnostics = io.StringIO()
    parent = child = None
    token = None
    started = time.monotonic()
    try:
        with contextlib.redirect_stdout(diagnostics), contextlib.redirect_stderr(diagnostics):
            sys.path.insert(0, job['native_source'])
            from hermes_constants import set_hermes_home_override
            from hermes_cli.auth_codex import resolve_codex_runtime_credentials
            set_hermes_home_override(job['credential_owner_home'])
            credentials = resolve_codex_runtime_credentials(refresh_if_expiring=False)
            token = checked_access_token(credentials)
            credentials.clear()
            set_hermes_home_override(os.environ['HERMES_HOME'])
            os.environ['TERMINAL_CWD'] = str(fixture)
            os.chdir(fixture)
            from run_agent import AIAgent
            from agent.system_prompt import build_system_prompt
            parent = AIAgent(model=job['model'], provider='openai-codex', api_mode='codex_responses',
                api_key=token, base_url='https://chatgpt.com/backend-api/codex',
                enabled_toolsets=['terminal', 'file'], skip_context_files=True, skip_memory=True,
                skip_background_review=True, load_soul_identity=False, quiet_mode=True,
                save_trajectories=False, fallback_model=None,
                reasoning_config={'enabled': True, 'effort': job['reasoning']},
                max_iterations=job['max_iterations'], run_budget_seconds=job['timeout'])
            plugin = load('artifact_routed_adapter', Path(job['source']) / 'integrations/hermes/routed-delegation/__init__.py')
            seam = plugin._private_runtime()
            task = {'id': job['id'], 'goal': job['prompt'], 'context': job['instructions'],
                    'toolsets': ['terminal', 'file'], 'role': 'leaf', 'route_request': job['route_request']}
            task['_native_envelope'] = plugin._v3_native_envelope(parent, task)
            pin = plugin._select_or_reuse_v3(parent.session_id, task, job['max_iterations'])
            result['routing'] = pin
            receipt = require_model(pin)
            child = plugin._prepare_child(parent, task, receipt, 0, 1, job['max_iterations'],
                build=seam['build'], validate_request=seam['validate_request'], budget_summary=seam['budget_summary'])
            plugin._guard_v3_child(child, task, pin)
            if child._delegate_role != 'leaf' or 'delegate_task' in child.valid_tool_names:
                raise ValueError('Artifact trials must be native leaf workers')
            child.run_budget_seconds = job['timeout']
            assembled = build_system_prompt(child)
            if token in assembled:
                raise ValueError('Credential appeared in prompt')
            result['prompt_sha256'] = plugin._sha(assembled)
            result['prompt_characters'] = len(assembled)
            result['exposed_tools'] = sorted(child.valid_tool_names)
            result['model_launched'] = True
            native = plugin._run_exact_child(seam['run'], 0, task, receipt, child, parent, {})
            result['native'] = {k: v for k, v in native.items() if not k.startswith('_')}
            result['ok'] = native.get('status') == 'completed' and native.get('exit_reason') == 'completed'
            result['active_children_remaining'] = len(seam['list_active']())
            if token in json.dumps(result):
                raise ValueError('Credential appeared in result')
    except BaseException as exc:
        import traceback
        result['ok'] = False
        result['error_type'] = type(exc).__name__
        result['error_locations'] = [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}
                                   for f in traceback.extract_tb(exc.__traceback__)]
    finally:
        with contextlib.redirect_stdout(diagnostics), contextlib.redirect_stderr(diagnostics):
            result['cleanup_errors'] = []
            for agent in (child, parent):
                if agent is not None:
                    try:
                        agent.close()
                    except BaseException as exc:
                        result['ok'] = False
                        result['cleanup_errors'].append(type(exc).__name__)
        result['seconds'] = time.monotonic() - started
        result['suppressed_diagnostic_characters'] = len(diagnostics.getvalue())
        # Detection must remove the unsafe payload, including on failure paths.
        # Retain only bounded controller metadata; never serialize native output.
        if token and token in json.dumps(result):
            result = {'ok': False, 'model_launched': result['model_launched'],
                      'lane': 'routed-artifact-pilot-v1', 'quality_admission': False,
                      'error_type': 'CredentialOutputRejected',
                      'cleanup_errors': result['cleanup_errors'], 'seconds': result['seconds']}
        token = None
        output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(output), 'ok': result['ok'], 'model_launched': result['model_launched']}))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
