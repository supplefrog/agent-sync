"""Read-only local Markdown link checker for this small fixture."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
missing = []
for path in [root / "AGENTS.md", *sorted((root / "docs").glob("*.md"))]:
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        if "://" not in target and not target.startswith("#"):
            name = target.split("#", 1)[0]
            if not (path.parent / name).exists():
                missing.append(f"{path.relative_to(root)}: {target}")
if missing:
    print("\n".join(missing))
    sys.exit(1)
print("Local documentation links resolve.")
