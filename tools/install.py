#!/usr/bin/env python
"""Install or verify admitted Agent Sync artifacts across supported hosts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

TRANSIENT_NAMES = {"__pycache__", ".pytest_cache", ".pytest-cache"}


def _codex_fleet_readback(executable, root, required):
    """Native skills/list + fs/readFile; no thread, turn or model request."""
    import base64
    import queue
    import threading
    messages = queue.Queue()
    process = subprocess.Popen([executable, 'app-server', '--stdio'], cwd=Path.home(),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf-8', creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def receive():
        for line in process.stdout:
            try: messages.put(json.loads(line))
            except ValueError: pass
        messages.put(None)
    reader = threading.Thread(target=receive,daemon=True);reader.start()
    def drain_diagnostics():
        for _ in process.stderr: pass
    discard = threading.Thread(target=drain_diagnostics,daemon=True);discard.start()
    sequence = 0
    def request(method, params):
        nonlocal sequence
        sequence += 1
        process.stdin.write(json.dumps({'id':sequence,'method':method,'params':params})+'\n');process.stdin.flush()
        import time
        deadline=time.monotonic()+30
        while True:
            value=messages.get(timeout=max(.01,deadline-time.monotonic()))
            if value is None: raise RuntimeError('Codex readback process closed before its reply')
            if value.get('method') and 'id' in value: raise RuntimeError('Codex readback requires an interactive action')
            if value.get('id')==sequence:
                if 'error' in value: raise RuntimeError('Codex native read-only request failed: '+method)
                return value['result']
    try:
        # Explicit auth is a connection-only capability: this readback must not
        # initiate a browser login. No standing configuration is written.
        request('initialize',{'clientInfo':{'name':'agent-sync-readback','version':'1'},
                              'capabilities':{'explicitGatewayOauth':True}})
        process.stdin.write(json.dumps({'method':'initialized'})+'\n');process.stdin.flush()
        catalog=request('skills/list',{'cwds':[str(Path.home())],'forceReload':True})
        entries=[row for group in catalog['data'] for row in group['skills'] if row.get('enabled',True)]
        by_name={row['name']:row for row in entries}
        reads={}
        for name in required:
            row=by_name.get(name)
            if not row or Path(row['path']).resolve()!=(root/name/'SKILL.md').resolve():
                reads[name]=False;continue
            content=request('fs/readFile',{'path':row['path']})
            data=base64.b64decode(content['dataBase64'],validate=True)
            reads[name]=data==(root/name/'SKILL.md').read_bytes()
        return {'names':sorted(by_name),'body_reads':reads,'thread_created':False,
                'catalog_sha256':hashlib.sha256(json.dumps(catalog,sort_keys=True).encode()).hexdigest()}
    except queue.Empty:
        raise RuntimeError('Codex read-only app-server request timed out')
    finally:
        process.stdin.close()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate();process.wait(timeout=5)
        reader.join(timeout=2);discard.join(timeout=2)
        process.stdout.close();process.stderr.close()


def verify_fleet_discovery(host: str, root: Path, required: list[str], retired: list[str]) -> dict:
    """Read fresh native catalogues and managed bodies without inference.

    This verifies global discovery/readability, not an already-running session's
    cached prompt or comparative behavior. Never retain assembled private input.
    """
    result = {'host': host, 'verified': False, 'model_calls': 0,
              'scope': 'fresh native global catalogue and managed-body readback; existing sessions may cache instructions'}
    try:
        if host == 'hermes':
            home = hermes_home(); runtime = home / 'hermes-agent'
            python = runtime / ('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
            code = """import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tools.skills_tool import find_all_skills,skill_view
from hermes_cli.config import load_config_readonly
root=Path(sys.argv[2]); required=json.loads(sys.argv[3]); retired=json.loads(sys.argv[4])
catalog=find_all_skills(); names=[x['name'] for x in catalog]
config=load_config_readonly(); dirs=config.get('skills',{}).get('external_dirs',[])
reads={}
for name in required:
    view=json.loads(skill_view(name,preprocess=False))
    text=view.get('content','').replace('\\r\\n','\\n')
    body=(root/name/'SKILL.md').read_text(encoding='utf-8').replace('\\r\\n','\\n')
    if body.startswith('---\\n'): body=body.split('---',2)[2]
    reads[name]=not view.get('error') and body.strip() in text
print(json.dumps({'names':names,'body_reads':reads,'root_configured':any(Path(x).expanduser().resolve()==root.resolve() for x in dirs)}))
"""
            p = subprocess.run([str(python), '-B', '-c', code, str(runtime), str(root), json.dumps(required), json.dumps(retired)],
                               capture_output=True, text=True, encoding='utf-8', timeout=45)
            if p.returncode: raise RuntimeError('Hermes native catalogue read failed')
            value = json.loads(p.stdout.splitlines()[-1]); names = set(value['names'])
            loaded = all(value['body_reads'].values()) and value['root_configured']
        elif host == 'codex':
            executable = shutil.which('codex.exe' if os.name == 'nt' else 'codex')
            if not executable and os.name == 'nt':
                directory = Path(os.environ['LOCALAPPDATA']) / 'OpenAI/Codex/bin'
                candidates = list(directory.glob('*/codex.exe'))
                candidates.sort(key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True)
                executable = str(candidates[0]) if candidates else None
            if not executable: raise RuntimeError('Codex native executable unavailable')
            value = _codex_fleet_readback(executable, root, required)
            names=set(value['names']);loaded=all(value['body_reads'].values())
            result.update(catalog_sha256=value['catalog_sha256'],thread_created=value['thread_created'])
        elif host == 'omp':
            executable = shutil.which('omp')
            if not executable: raise RuntimeError('OMP native executable unavailable')
            p = subprocess.run([executable, '--mode', 'rpc', '--no-session'],
                               input=json.dumps({'type':'get_available_commands','id':'agent-sync-readback'})+'\n',
                               cwd=Path.home(), capture_output=True, text=True, encoding='utf-8', timeout=45)
            messages = []
            for line in p.stdout.splitlines():
                try: messages.append(json.loads(line))
                except ValueError: pass
            replies = [v for v in messages if v.get('id')=='agent-sync-readback' and v.get('success') is True]
            if p.returncode or len(replies)!=1: raise RuntimeError('OMP native catalogue read failed')
            names = {v['name'].removeprefix('skill:') for v in replies[0]['data']['commands'] if v.get('source')=='skill'}
            loaded = True
            for name in required:
                path = root/name/'SKILL.md'
                view = subprocess.run([executable, 'read', str(path)+':raw'], cwd=Path.home(), capture_output=True,
                                      text=True, encoding='utf-8', timeout=30)
                loaded = loaded and view.returncode==0 and view.stdout.replace('\r\n','\n').strip()==path.read_text(encoding='utf-8').replace('\r\n','\n').strip()
        else:
            raise RuntimeError('Unsupported configured host: ' + host)
        result.update(required_present=sorted(set(required)&names), required_missing=sorted(set(required)-names),
                      retired_offered=sorted(set(retired)&names), loading_verified=bool(loaded))
        result['verified'] = not result['required_missing'] and not result['retired_offered'] and bool(loaded)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        result['reason'] = str(exc)[:300]
    return result


def verify_generated_instructions(repo: Path, adapters: dict) -> None:
    if any(adapter["instructions"]["strategy"] == "generated" for adapter in adapters.values()):
        import render_instructions
        try:
            render_instructions.verify(repo)
        except render_instructions.RenderError as exc:
            raise RuntimeError(str(exc)) from exc


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def hermes_home() -> Path:
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"]).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "hermes"
    return Path.home() / ".hermes"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def shared_skills_home() -> Path:
    return Path.home() / ".agents" / "skills"


def omp_home() -> Path:
    return Path.home() / ".omp" / "agent"


def adapter_variables() -> dict[str, str]:
    return {
        "HOME": str(Path.home()),
        "CODEX_HOME": str(codex_home()),
        "HERMES_HOME": str(hermes_home()),
        "SHARED_SKILLS_HOME": str(shared_skills_home()),
        "OMP_HOME": str(omp_home()),
    }


def adapter_path(template: str) -> Path:
    return Path(template.format_map(adapter_variables())).expanduser()


def load_adapter(repo: Path, host: str) -> dict[str, object]:
    path = repo / "adapters" / f"{host}.json"
    adapter = json.loads(path.read_text(encoding="utf-8"))
    if adapter.get("schema_version") != 1 or adapter.get("host") != host:
        raise RuntimeError(f"invalid adapter: {path}")
    return adapter


def same_content(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and digest(a) == digest(b)


def is_linklike(path: Path) -> bool:
    if not os.path.lexists(path):
        return False
    attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    return os.path.islink(path) or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def tree_record(root: Path) -> tuple[tuple[str, str, str], ...] | None:
    if not root.is_dir() or is_linklike(root):
        return None
    entries: list[tuple[str, str, str]] = []
    for path in sorted(root.rglob("*")):
        if is_linklike(path):
            return None
        relative = path.relative_to(root).as_posix()
        if any(part in TRANSIENT_NAMES for part in path.relative_to(root).parts) or path.suffix == ".pyc":
            continue
        if path.is_dir():
            entries.append(("directory", relative, ""))
        elif path.is_file():
            entries.append(("file", relative, digest(path)))
        else:
            return None
    return tuple(entries)


def same_tree(a: Path, b: Path) -> bool:
    a_record = tree_record(a)
    return a_record is not None and a_record == tree_record(b)


def expose_surface(source: Path, target: Path, force: bool, copy_only: bool) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink() and target.resolve() == source.resolve():
            return "linked"
        if not force and not same_content(source, target):
            raise RuntimeError(f"refusing to replace different file: {target}; use --force")
        target.unlink()
    if copy_only:
        shutil.copy2(source, target)
        return "copied"
    try:
        target.symlink_to(source)
        return "symlinked"
    except OSError:
        try:
            os.link(source, target)
            return "hardlinked"
        except OSError:
            shutil.copy2(source, target)
            return "copied"


def expose_skill(source: Path, target: Path, force: bool) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.resolve() == source.resolve():
        return "native"
    if target.exists() or target.is_symlink():
        if target.is_symlink() and target.resolve() == source.resolve():
            return "linked"
        if same_tree(source, target):
            return "matching"
        if not force:
            raise RuntimeError(f"refusing to replace different skill: {target}; use --force")
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    try:
        target.symlink_to(source, target_is_directory=True)
        return "symlinked"
    except OSError as exc:
        if sys.platform == "win32":
            junction = run(["cmd", "/c", "mklink", "/J", str(target), str(source)])
            if junction.returncode == 0:
                return "junction"
        raise RuntimeError(f"cannot link {target} to {source}: {exc}") from exc


def expose_skills(
    repo_skills: Path,
    force: bool,
    target_root: Path | None = None,
    names: set[str] | None = None,
    copy_mode: bool = False,
) -> list[tuple[str, str]]:
    target_root = target_root or shared_skills_home()
    target_root.mkdir(parents=True, exist_ok=True)
    statuses: list[tuple[str, str]] = []
    for source in sorted(repo_skills.iterdir()):
        if not source.is_dir() or not (source / "SKILL.md").is_file():
            continue
        if names is not None and source.name not in names:
            continue
        target = target_root / source.name
        if copy_mode:
            if target.exists() or target.is_symlink():
                if target.is_symlink():
                    target.unlink()
                elif sys.platform == "win32" and target.is_dir() and target.resolve() == source.resolve():
                    os.rmdir(target)
                elif target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.copytree(source, target)
            statuses.append((source.name, "copied"))
        else:
            statuses.append((source.name, expose_skill(source, target, force)))
    return statuses


def registry_statuses(repo: Path) -> dict[str, str]:
    registry = json.loads((repo / "registry.json").read_text(encoding="utf-8"))
    return {str(item["name"]): str(item["status"]) for item in registry["skills"]}


def parse_list(raw: str) -> list[str]:
    raw = raw.strip()
    for parser in (json.loads, ast.literal_eval):
        try:
            value = parser(raw)
            if isinstance(value, list):
                return [str(item) for item in value]
        except Exception:
            pass
    return []


def configure_hermes(skills_root: Path, key: str = "skills.external_dirs") -> str:
    hermes = shutil.which("hermes")
    if not hermes:
        return "not installed"
    current = run([hermes, "config", "get", key])
    if current.returncode:
        raise RuntimeError(current.stderr or current.stdout)
    canonical = str(skills_root.resolve())
    paths = parse_list(current.stdout)
    # Older Hermes CLI builds can quote JSON arrays as one YAML scalar. Repair
    # that representation through a safe YAML rewrite so runtime discovery sees
    # an actual list rather than the literal string '["..."]'.
    try:
        import yaml

        config_path_result = run([hermes, "config", "path"])
        config_path = Path(config_path_result.stdout.strip())
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        cursor = config
        parts = key.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        raw_value = cursor.get(parts[-1])
        if isinstance(raw_value, str):
            repaired = parse_list(raw_value)
            if repaired:
                paths = repaired
                cursor[parts[-1]] = paths
                config_path.write_text(
                    yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
        elif isinstance(raw_value, list):
            paths = [str(item) for item in raw_value]
    except (OSError, ValueError, TypeError):
        pass
    if not any(Path(path).expanduser().resolve() == skills_root.resolve() for path in paths):
        paths.append(canonical)
        changed = run([hermes, "config", "set", key, json.dumps(paths)])
        if changed.returncode:
            raise RuntimeError(changed.stderr or changed.stdout)
        # Re-enter once to repair scalar quoting produced by affected clients.
        return configure_hermes(skills_root, key)
    return "configured"


def doctor(repo: Path, hosts: set[str] | None = None) -> int:
    failures = 0
    statuses = registry_statuses(repo)
    hosts = hosts or {"codex", "hermes", "omp"}
    adapters = {host: load_adapter(repo, host) for host in hosts}
    verify_generated_instructions(repo, adapters)
    roots = {
        host: adapter_path(adapter["skills"]["install_root"]).resolve()
        for host, adapter in adapters.items()
    }

    for host, target_skills in sorted(roots.items()):
        for skill in sorted((repo / "skills").iterdir()):
            if not skill.is_dir() or not (skill / "SKILL.md").is_file():
                continue
            target = target_skills / skill.name
            activated = target.exists() and (
                target.resolve() == skill.resolve()
                or same_tree(target, skill)
            )
            if statuses.get(skill.name) == "admitted":
                print(("PASS" if activated else "FAIL"), f"admitted skill {skill.name}", "->", target)
                failures += not activated
            elif activated:
                print("FAIL", f"staged skill {skill.name} is active", "->", target)
                failures += 1

    for host, adapter in adapters.items():
        instruction = adapter["instructions"]
        if instruction["strategy"] == "manual-merge":
            target = adapter_path(instruction["target"])
            markers = instruction.get("required_markers", [])
            if not markers:
                print("SKIP", f"{host} manual-merge markers not declared", "->", target)
                continue
            try:
                content = target.read_text(encoding="utf-8")
            except OSError:
                content = ""
            ok = all(marker in content for marker in markers)
            print(("PASS" if ok else "FAIL"), f"{host} manual-merge markers", "->", target)
            failures += not ok
            continue
        if instruction["strategy"] == "inherit-codex":
            print("PASS", f"{host} surface strategy", "->", instruction["strategy"])
            continue
        target = adapter_path(instruction["target"])
        expected = repo / instruction["source"]
        ok = same_content(target, expected)
        print(("PASS" if ok else "FAIL"), f"{host} surface", "->", target)
        failures += not ok

    hermes = shutil.which("hermes")
    if "hermes" in adapters and hermes:
        discovery = adapters["hermes"]["skills"]["discovery"]
        key = discovery["key"]
        expected_root = adapter_path(discovery["value"])
        result = run([hermes, "config", "get", key])
        entries = parse_list(result.stdout) if result.returncode == 0 else []
        try:
            import yaml

            config_path_result = run([hermes, "config", "path"])
            config = yaml.safe_load(Path(config_path_result.stdout.strip()).read_text(encoding="utf-8")) or {}
            raw_entries = config
            for part in key.split("."):
                raw_entries = raw_entries.get(part, {}) if isinstance(raw_entries, dict) else {}
            if isinstance(raw_entries, list):
                entries = [str(item) for item in raw_entries]
        except (OSError, ValueError, TypeError):
            pass
        ok = any(Path(path).expanduser().resolve() == expected_root.resolve() for path in entries)
        print(("PASS" if ok else "FAIL"), "Hermes shared skills directory")
        failures += not ok
    elif "hermes" in adapters:
        print("SKIP Hermes shared skills directory (Hermes not installed)")


    validate = run([sys.executable, str(repo / "tools" / "validate.py")])
    print(validate.stdout, end="")
    failures += validate.returncode != 0
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", choices=("install", "doctor"), default="install")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--copy-surfaces", action="store_true")
    parser.add_argument("--agents", default="codex,hermes,omp")
    args = parser.parse_args()
    repo = args.repo.resolve()
    agents = {item.strip() for item in args.agents.split(",") if item.strip()}
    supported = {"codex", "hermes", "omp"}
    unknown = agents - supported
    if unknown:
        raise RuntimeError("unsupported agent(s): " + ", ".join(sorted(unknown)))

    if args.action == "doctor":
        return doctor(repo, agents)

    adapters = {host: load_adapter(repo, host) for host in agents}
    verify_generated_instructions(repo, adapters)
    statuses = registry_statuses(repo)
    admitted = {name for name, status in statuses.items() if status == "admitted"}
    if any(
        adapter["instructions"]["strategy"] == "link-or-copy"
        for host, adapter in adapters.items()
    ):
        required_surface_skills = {"capability-curator", "surface-convergence"}
        missing_surface_skills = required_surface_skills - admitted
        if missing_surface_skills:
            missing = ", ".join(sorted(missing_surface_skills))
            raise RuntimeError(f"shared surface requires staged skill(s) {missing}; admit them before installation")

    exposed_roots: set[Path] = set()
    for host, adapter in sorted(adapters.items()):
        skills = adapter["skills"]
        target_skills = adapter_path(skills["install_root"])
        if target_skills.resolve() not in exposed_roots:
            for name, status in expose_skills(
                repo / skills["source"],
                args.force,
                target_skills,
                admitted,
                copy_mode=False,
            ):
                print(f"skill {name}:", status)
            exposed_roots.add(target_skills.resolve())
        discovery = skills["discovery"]
        if discovery["kind"] == "config-list" and host == "hermes":
            print(f"{host} skills:", configure_hermes(adapter_path(discovery["value"]), discovery["key"]))
        manifest = adapter.get("manifest")
        if manifest:
            manifest_source = repo / manifest["source"]
            manifest_target = adapter_path(manifest["target"])
            manifest_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(manifest_source, manifest_target)
            print(f"{host} manifest: copied")

        instruction = adapter["instructions"]
        if instruction["strategy"] in {"manual-merge", "inherit-codex"}:
            print(f"{host} surface: {instruction['strategy']}")
            continue
        source = repo / instruction["source"]
        target = adapter_path(instruction["target"])
        print(f"{host} surface:", expose_surface(source, target, args.force, args.copy_surfaces))
    return doctor(repo, agents)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
