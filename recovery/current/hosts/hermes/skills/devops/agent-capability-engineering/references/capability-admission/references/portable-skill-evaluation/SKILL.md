---
name: portable-skill-evaluation
description: Compare, validate, and normalize portable agent skill formats across platforms. Use when researching official skill specs, evaluating skill packaging/trigger mechanisms, or deciding how to represent one reusable skill across Hermes, Codex, Claude/Anthropic, or similar agent runtimes.
---

# Portable Skill Evaluation

Use this skill when the task is to understand or compare official skill mechanisms across agent runtimes, or to decide what belongs in the smallest interoperable skill format.

## Core goal
Preserve the smallest portable core while separating platform-specific metadata and validation into adapters.

## Workflow
1. Identify the portable minimum:
   - one `SKILL.md`
   - YAML frontmatter with `name` and `description` only
   - concise imperative body
2. Separate portable vs platform-specific content:
   - keep reusable procedure in `SKILL.md`
   - move heavy detail to `references/`
   - move deterministic checks to `scripts/`
   - move starter artifacts to `templates/`
   - move output-only assets to `assets/`
3. Capture canonical mechanisms from primary sources:
   - exact file layout
   - trigger rules
   - validation or generation commands
   - packaging or manifest hooks
4. Prefer official repositories and source files when docs are blocked or incomplete.
5. Record the adapter-specific metadata separately from the portable core.

## What to extract
- minimal file layout that works across runtimes
- the exact fields that actually trigger loading
- validation scripts or schema checks
- package/manifest rules that expose skills to the runtime
- forward-testing patterns that prove the skill works on real artifacts

## What not to do
- Do not bloat the portable core with product-specific UI metadata.
- Do not mirror full upstream docs into the skill body.
- Do not treat secondary summaries as canonical evidence.

## Evaluation guidance
When comparing official implementations, report:
- canonical URLs
- exact files or manifests involved
- the smallest interoperable form
- any runtime-specific extensions that should stay in adapters

## Support files
- See `references/portable-skills-research.md` for condensed source-backed notes and canonical URLs.
- Add `scripts/` for deterministic validators or probes.
- Add `templates/` only for reusable scaffolds.
