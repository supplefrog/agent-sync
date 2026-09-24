"""Credential-free native assembly probe. No conversation or model tool dispatch.

The offline route substitute and safe-mode omissions are recorded limitations,
not parity evidence. Python audit guards bound this trusted construction probe;
they are NOT a sandbox for model-generated programs, subprocesses or plugins.
"""
from __future__ import annotations

import contextlib
import functools
import io
import json
import os
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

from evaluation_native_diagnostic import digest, encode, locate_sources, owned, save_new


class ProbeBoundary(BaseException):
    """Native best-effort Exception handlers must not swallow probe boundaries."""


class AssemblyGuard:
    def __init__(self, root, native, violations):
        self.root = root.resolve()
        self.read_roots = [self.root, native.resolve(), Path(sys.base_prefix).resolve(),
                           Path(__file__).resolve().parent]
        self.violations = violations

    def deny(self, event, reason):
        self.violations.append({'event': event, 'reason': reason})
        raise ProbeBoundary(reason)

    def check_path(self, event, value, writing=False):
        if not isinstance(value, (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(value)).resolve()
        if str(path) == os.devnull or os.fsdecode(value).lower() == 'nul':
            return
        if path.name.lower() in ('.env', 'auth.json', 'credentials.json', 'auth.db'):
            self.deny(event, 'credential-file-access')
        roots = [self.root] if writing else self.read_roots
        if not any(path.is_relative_to(root) for root in roots):
            self.deny(event, 'outside-owned-write' if writing else 'unstaged-file-read')

    def __call__(self, event, args):
        if event.startswith('socket.') and event not in ('socket.__new__', 'socket.gethostname'):
            self.deny(event, 'network-attempt')
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.fork', 'os.forkpty', 'os.spawn'):
            self.deny(event, 'subprocess-attempt')
        if event == 'open':
            mode, flags = args[1:3]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
            self.check_path(event, args[0], writing)
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.truncate', 'sqlite3.connect'):
            self.check_path(event, args[0], True)
        elif event in ('os.rename', 'os.link', 'os.symlink'):
            for value in args[:2]:
                self.check_path(event, value, True)
        elif event == 'os.chdir':
            self.check_path(event, args[0], True)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from strings(item)


def observer(function, records):
    source = Path(function.__code__.co_filename).name + ':' + str(function.__code__.co_firstlineno) + ':' + function.__name__

    @functools.wraps(function)
    def call(*args, **kwargs):
        value = function(*args, **kwargs)
        records.extend({'source': source, 'text': text} for text in strings(value) if text)
        return value
    return call


def main():
    transport = sys.stdout
    diagnostics = io.StringIO()
    job = json.loads(sys.stdin.readline())
    if job.get('mode') != 'assemble-only' or set(job) != {
            'mode', 'root', 'home', 'fixture', 'native_source', 'route', 'id'}:
        raise ValueError('only an assembly-only job is accepted; inference is unsupported')
    root, home, fixture = (Path(job[k]).resolve() for k in ('root', 'home', 'fixture'))
    for path in (home, fixture):
        if not path.is_relative_to(root) or not path.is_dir():
            raise ValueError('unowned or missing home/fixture')
    if Path(os.environ['HERMES_HOME']).resolve() != home or Path(os.environ['TERMINAL_CWD']).resolve() != fixture:
        raise ValueError('runtime bindings differ from job')
    if job['route']['provider'] != 'openai-codex':
        raise ValueError('unsupported diagnostic route')
    agent = db = None
    result = {'assembled': False, 'violations': [], 'model_requests': 0,
              'native_handles_closed': False, 'launch_permitted': False,
              'route_resolution': 'declared-offline-substitute', 'guard_installed': False,
              'conversation_started': False, 'session_rows_created': False}
    guard = AssemblyGuard(root, Path(job['native_source']), result['violations'])
    # Before ANY native import: no credentials, network, children or live writes.
    sys.addaudithook(guard)
    result['guard_installed'] = True
    try:
        with contextlib.redirect_stdout(diagnostics), contextlib.redirect_stderr(diagnostics):
            sys.path.insert(0, job['native_source'])
            from hermes_constants import set_hermes_home_override
            set_hermes_home_override(str(home))
            os.chdir(fixture)
            from hermes_state import SessionDB
            from tui_gateway import server
            from agent import system_prompt
            db = SessionDB(home / 'state.db')
            runtime = {'provider': 'openai-codex', 'api_mode': 'codex_responses',
                       'base_url': 'https://chatgpt.com/backend-api/codex',
                       'api_key': 'diagnostic-placeholder-not-a-credential'}
            # Declared credential-free construction seam. Native routing is NOT
            # attested by this substitute and the receipt cannot authorize calls.
            with patch.object(server, '_resolve_agent_model_runtime', return_value=(job['route']['model'], runtime)):
                agent = server._make_agent(job['id'], job['id'], session_db=db,
                    model_override={'model': job['route']['model'], 'provider': 'openai-codex'},
                    reasoning_config_override={'enabled': True, 'effort': job['route']['reasoning']},
                    service_tier_override='', platform_override='desktop', context_cwd_is_launch_artifact=False)
            fragments = []
            with contextlib.ExitStack() as stack:
                for name in ('_identity_parts', '_guidance_parts', '_coding_parts', '_context_files_part',
                             '_post_workspace_parts', '_skills_prompt', '_memory_parts', '_timestamp_line'):
                    original = getattr(system_prompt, name)
                    stack.enter_context(patch.object(system_prompt, name, observer(original, fragments)))
                tiers = system_prompt.build_system_prompt_parts(agent)
            prompt = '\n\n'.join(tiers[key] for key in ('stable', 'context', 'volatile') if tiers[key])
            origins = locate_sources(prompt, fragments)
            result.update(assembled=True, prompt_sha256=digest(prompt.encode('utf-8')),
                tools_sha256=digest(encode(agent.tools)), source_spans=len(origins),
                tiers=tiers, assembled_prompt=prompt, source_map=origins,
                fragments=fragments, tools=agent.tools, exposed_tools=sorted(agent.valid_tool_names),
                ephemeral_prompt=agent.ephemeral_system_prompt,
                communication_skill_discovered='- conversational-communication:' in prompt,
                communication_skill_body_loaded=False,
                constructor_route={'model': agent.model, 'provider': agent.provider,
                                   'reasoning': agent.reasoning_config.get('effort')},
                interpreter=sys.executable)
    except BaseException as exc:
        result['error_type'] = type(exc).__name__
        if isinstance(exc, ProbeBoundary):
            result['boundary_reason'] = str(exc)
        result['error_locations'] = [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}
                                     for f in traceback.extract_tb(exc.__traceback__)]
    finally:
        with contextlib.redirect_stdout(diagnostics), contextlib.redirect_stderr(diagnostics):
            try:
                if agent is not None:
                    agent.close()
                if db is not None:
                    db.close()
                result['native_handles_closed'] = True
            except BaseException as exc:
                result['cleanup_error'] = type(exc).__name__
        result['suppressed_diagnostic_characters'] = len(diagnostics.getvalue())
        save_new(owned(root, 'worker.json'), result)
    print(json.dumps({'finished': True, 'assembled': result['assembled'],
                      'error_type': result.get('error_type')}), file=transport, flush=True)
    return 0 if result['assembled'] and not result['violations'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
