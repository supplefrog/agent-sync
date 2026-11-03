"""Read-only, request-scoped access to skills withheld from shared discovery."""
from __future__ import annotations

import argparse
import json
import os
import re
from functools import lru_cache
from pathlib import Path

NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
START = "<!-- agent-sync-model-skill:"
END = "<!-- /agent-sync-model-skill -->"
BODY = re.compile(r"<!-- agent-sync-model-skill:([a-z0-9-]+) -->.*?(?:<!-- /agent-sync-model-skill -->|$)", re.S)
CATALOG = re.compile(r"<!-- agent-sync-model-skill-catalog -->.*?(?:<!-- /agent-sync-model-skill-catalog -->|$)", re.S)
HIDDEN = "[Skill unavailable for the current model.]"


def source_root() -> Path:
    shared = Path(os.environ.get("AGENT_SYNC_SHARED_SKILLS", Path.home() / ".agents/skills"))
    state = json.loads((shared / ".agent-signal-fleet.json").read_bytes())
    snapshot = Path(state["source_snapshot"])
    if not snapshot.is_absolute() or snapshot.parts[-2:] != ("render", "fleet"):
        raise ValueError("invalid managed source origin")
    return snapshot.parent.parent


@lru_cache(maxsize=8)
def _json(path: str, mtime: int, size: int):
    return json.loads(Path(path).read_bytes())


def read_json(path: Path):
    st = path.stat()
    if st.st_size > 2_000_000:
        raise ValueError("oversized model policy")
    return _json(str(path), st.st_mtime_ns, st.st_size)


class Runtime:
    def __init__(self, source: Path | None = None):
        self.source = source

    def root(self) -> Path:
        return self.source if self.source is not None else source_root()

    def managed_names(self) -> set[str]:
        try:
            policy = read_json(self.root() / "contracts/skill-model-policy.json")
            return {name for name in policy["skills"] if isinstance(name, str) and NAME.fullmatch(name)} if policy.get("schema_version") == 1 else set()
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return set()

    def available(self, host: str, provider: str, model: str) -> list[dict]:
        try:
            root = self.root()
            policy = read_json(root / "contracts/skill-model-policy.json")
            catalog = read_json(root / "contracts/model-weights.json")
            if policy.get("schema_version") != 1 or catalog.get("schema_version") != 1:
                return []
            if not isinstance(provider, str) or not isinstance(model, str) or not provider or not model:
                return []
            models = catalog.get("open_weight_models", {}).get(provider, [])
            if not isinstance(models, list) or not all(isinstance(item, str) for item in models) or model not in models:
                return []
            rows = []
            for name, rule in policy["skills"].items():
                if not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(rule, dict):
                    continue
                hosts = rule.get("hosts")
                if rule.get("requires") != "open-weights" or not isinstance(hosts, list) or host not in hosts:
                    continue
                entry = self._path(root, name, "SKILL.md").read_text(encoding="utf-8")
                description = re.search(r"^description: ([^\r\n]+)", entry, re.M)
                if description:
                    rows.append({"name": name, "description": description[1].strip()})
            return rows
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return []

    @staticmethod
    def _path(root: Path, name: str, relative: str) -> Path:
        if not NAME.fullmatch(name) or not isinstance(relative, str) or "\\" in relative:
            raise ValueError("invalid skill address")
        parts = relative.split("/")
        if any(part in ("", ".", "..") for part in parts) or Path(relative).is_absolute():
            raise ValueError("invalid skill address")
        base = root / "skills" / name
        target = base.joinpath(*parts)
        for path in (base, *target.parents):
            if path == root:
                break
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError("linked skill path")
        if target.is_symlink() or not target.resolve(strict=True).is_relative_to(base.resolve(strict=True)):
            raise ValueError("escaping skill path")
        if target.stat().st_size > 128_000:
            raise ValueError("oversized skill file")
        return target

    def view(self, host: str, provider: str, model: str, name: str, file_path: str | None = None) -> dict:
        if not isinstance(name, str):
            return {"success": False, "error": "Skill not available for the current model."}
        allowed = {row["name"] for row in self.available(host, provider, model)}
        if name not in allowed:
            return {"success": False, "error": "Skill not available for the current model."}
        try:
            text = self._path(self.root(), name, file_path or "SKILL.md").read_text(encoding="utf-8")
            return {"success": True, "name": name, "_agent_sync_model_skill": name, "content": f"{START}{name} -->\n{text}\n{END}"}
        except (OSError, ValueError, UnicodeError):
            return {"success": False, "error": "Skill file unavailable."}


def scrub(value, allowed: set[str]):
    """Transform only our marked material in the outbound copy, never the transcript."""
    hidden = object()

    def walk(item):
        if isinstance(item, str):
            if '"_agent_sync_model_skill"' in item:
                try:
                    parsed = json.loads(item)
                    result = walk(parsed)
                    return json.dumps({"success": False, "error": HIDDEN} if result is hidden else result)
                except ValueError:
                    pass
            item = CATALOG.sub("", item)
            return BODY.sub(lambda m: m[0] if m[1] in allowed else HIDDEN, item)
        if isinstance(item, list):
            return [v for v in (walk(v) for v in item) if v is not hidden]
        if isinstance(item, dict):
            if "_agent_sync_model_skill" in item and (not isinstance(item.get("_agent_sync_model_skill"), str) or item["_agent_sync_model_skill"] not in allowed):
                return hidden
            result = {key: walk(v) for key, v in item.items()}
            result = {key: v for key, v in result.items() if v is not hidden}
            if isinstance(item.get("skills"), list) and len(result["skills"]) != len(item["skills"]):
                result["count"] = len(result["skills"])
                result["categories"] = sorted({row["category"] for row in result["skills"] if isinstance(row, dict) and row.get("category")})
            return result
        return item

    result = walk(value)
    return {"success": False, "error": HIDDEN} if result is hidden else result


def catalog_text(rows: list[dict], loader: str) -> str:
    if not rows:
        return ""
    lines = ["<!-- agent-sync-model-skill-catalog -->", "<model_skills>"]
    lines.extend(f"{row['name']}: {row['description']}" for row in rows)
    lines.extend([f"Read an applicable skill with {loader}; use file_path for its references.", "</model_skills>", "<!-- /agent-sync-model-skill-catalog -->"])
    return "\n".join(lines)


def tool_enabled(request: dict, name: str) -> bool:
    if not isinstance(request.get("tools"), list):
        return False
    return any(isinstance(tool, dict) and (tool.get("name") == name or
               isinstance(tool.get("function"), dict) and tool["function"].get("name") == name)
               for tool in request["tools"])


def attach_catalog(request: dict, text: str) -> dict:
    if not text:
        return request
    if isinstance(request.get("instructions"), str):
        request["instructions"] += "\n\n" + text
    elif "system" in request:
        if isinstance(request["system"], str):
            request["system"] += "\n\n" + text
        elif isinstance(request["system"], list):
            request["system"] = [*request["system"], {"type": "text", "text": text}]
    elif isinstance(request.get("messages"), list):
        messages = request["messages"]
        if messages and messages[0].get("role") in ("system", "developer"):
            content = messages[0].get("content")
            if isinstance(content, str):
                messages[0]["content"] += "\n\n" + text
            elif isinstance(content, list):
                messages[0]["content"] = [*content, {"type": "text", "text": text}]
        else:
            request["messages"] = [{"role": "system", "content": text}, *messages]
    elif isinstance(request.get("input"), list):
        request["instructions"] = text
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "view"])
    parser.add_argument("--host", required=True, choices=["hermes", "omp", "codex"])
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--name", default="")
    parser.add_argument("--file-path")
    args = parser.parse_args()
    runtime = Runtime()
    result = runtime.available(args.host, args.provider, args.model) if args.action == "list" else runtime.view(args.host, args.provider, args.model, args.name, args.file_path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
