# Portable skills research notes

Use this when comparing official skill specs or deciding the smallest interoperable format.

## Portable minimum
- `SKILL.md` with YAML frontmatter containing only `name` and `description`
- A concise imperative body
- Optional support directories: `references/`, `scripts/`, `templates/`, `assets/`

## Canonical mechanisms worth preserving
- **Triggering:** the description is the primary trigger surface.
- **Progressive disclosure:** keep the main skill lean; move bulk detail into references.
- **Validation:** use a deterministic validator for structure plus forward-testing on realistic artifacts.
- **Adapter metadata:** keep product-specific UI/runtime metadata outside the portable core.

## Source-backed patterns
- **Hermes:** catalog/skill docs are generated from repo source; keep skills compact and use linked support files for depth.
- **OpenAI Codex:** built-in sample uses `agents/openai.yaml` for UI metadata, `scripts/quick_validate.py` for structural checks, and `scripts/init_skill.py` / `generate_openai_yaml.py` for deterministic scaffolding.
- **Anthropic / Claude Code:** skill bundles can be shipped inside plugins; skills are exposed through plugin manifests and a curated skill list, with package-level metadata staying separate from the SKILL body.

## Research rule
When official web docs are blocked or incomplete, inspect official repositories and sample files first, then cite the canonical doc URL alongside the repository path or sample file that proves the mechanism.