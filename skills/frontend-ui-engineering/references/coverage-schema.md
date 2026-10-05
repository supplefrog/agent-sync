# Frontend coverage acceptance

Use `scripts/frontend_coverage.py` to check that a declared requirement catalog is completely classified and that required cases have linked evidence for the intended revision and context. This supplements `frontend_gate.py`; its four measurement checks and legacy CLI are unchanged. Coverage validation does not inspect a browser or determine whether observations are true.

Python 3.11+ standard library only. From the skill's scripts directory, using absolute input paths in project work:

```powershell
python -B frontend_coverage.py catalog.json contract.json observations.json evidence-directory --previous previous-contract.json
python -B -m unittest -v test_frontend_coverage.py test_frontend_gate.py
```

`--previous` is optional. The CLI reads inputs and evidence metadata without modifying them. It emits JSON and exits `0` for pass, `1` for a retained failure, or `2` for incomplete inputs/coverage/evidence. A failure takes precedence over incomplete, retaining both kinds of finding. `coverage_status`, `measurement_status`, `checks`, `measurement_checks` and `ready` remain separate. `ready` is true only when applicable coverage passes and supplied/linked measurement checks pass. An absent measurement report is not applicable only when no case declares measurement links.

## Plan without rewriting classifications

```powershell
python -B frontend_coverage.py --plan --scope product --source-sha256 ACTUAL64HEXSOURCEHASH --features reader,chapter-reader --selected I21 ../references/regression-catalog.json
```

Plan mode takes only the catalog. Features and selected capability IDs are comma-separated lists; an omitted list is empty. It returns `{status: "incomplete", ready: false, contract: {...}, checks: [...]}` and exit `2`. Use the returned `contract` as a scaffold in the existing acceptance record. Classifications/reasons are inferred from the catalog and supplied feature inventory. Every required suffix is retained, methods are assigned cyclically to cover the catalog methods, and viewport/modality/state are intentionally empty. Rows with too few case suffixes to cover their methods are reported as unplannable rather than inventing IDs. Unknown feature tags, unknown/non-capability selections, duplicates and malformed catalogs are incomplete.

The collector must check the actual feature inventory against the DOM/source and user brief; plan mode cannot discover features or prove absence. Use exact mechanism tags for conditional rows, such as an actual local scroller or native select, rather than a broad page category that could hide applicable cases. Adjust the scaffold's case methods where appropriate, fill real scenario contexts, and collect linked observations before verification. Empty contexts or unmeasured evidence cannot pass. This reduces mechanical classification work; it does not choose treatments, relax requirements or impose a feature quota.

## Catalog

Use the full [regression-catalog.json](regression-catalog.json) owned by this skill for accumulated reusable requirements; do not trim it to the cases a build happens to pass. A project can extend that catalog locally for its brief, retaining all owner IDs. Do not maintain two independent copies of the brief. Every catalog item must have a contract classification, even when its feature is absent. IDs and case suffixes are unique nonempty strings; a case suffix is scoped by its requirement ID.

```json
{
  "schema_version": 1,
  "requirements": [
    {
      "id": "control-feedback",
      "class": "requirement",
      "features": ["common"],
      "methods": ["browser", "rendered"],
      "cases": ["pointer", "paint"],
      "summary": "Control feedback remains usable and belongs to the chosen visual system."
    }
  ]
}
```

`class` is `requirement`, `capability`, `conditional`, `tentative` or `project`. `features` contains unique feature tags; `common` applies to every product. `methods` is a nonempty unique list selected from `browser`, `rendered`, `source`, `resource`, `human`. Every required requirement must cover all its declared methods across its cases; the caller chooses a method for each case. `cases` is a nonempty unique list of case suffixes. `summary` is nonempty. Unknown/duplicate requirement or case IDs are incomplete.

## Contract

```json
{
  "schema_version": 1,
  "scope": "product",
  "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "features": ["reader"],
  "selected": [],
  "requirements": [
    {
      "id": "control-feedback",
      "disposition": "required",
      "cases": [
        {
          "id": "pointer",
          "method": "browser",
          "context": {"viewport": "320x900", "modality": "pointer", "state": "closed"},
          "measurement_ids": ["trigger-stability"]
        },
        {
          "id": "paint",
          "method": "rendered",
          "context": {"viewport": "320x900", "modality": "keyboard", "state": "focused"}
        }
      ]
    }
  ]
}
```

`scope` is `product` or `workflow`. `source_sha256` is exactly 64 hexadecimal characters and must match observation hashes exactly. `features` and `selected` are unique string lists. Unknown feature tags are incomplete in both planning and verification. `selected` contains catalog capability IDs, not other classes or effect names invented by a worker.

Applicability is determined by the catalog and scope:

| Catalog class | Product scope | Workflow evaluation scope |
| --- | --- | --- |
| requirement / conditional | Required when tagged common or a tag intersects product features; otherwise not_applicable | Required |
| capability | Required only when its ID is selected; otherwise unselected | Required |
| tentative | tentative | tentative |
| project | project | project |

Every item must have the resulting `disposition`. Non-required entries need a nonempty `reason` and `cases: []`. An optional unselected effect or absent feature does not force a product feature. Workflow evaluation intentionally exercises requirements, capabilities and conditional checks across representative cases; it does not mandate every feature in one product.

For a workflow portfolio with several fixtures, bind `source_sha256` to a deterministic manifest of their individually verified file hashes. Put the fixture identity and its source hash in each case's context and retain that manifest with the evidence. This lets different cases use different artifacts without silently treating one demo as proof of every capability. A fixture change invalidates the manifest; compare inherited cases and rerun the affected observations. The checker validates the declared bindings; the parent still verifies actual file identities and the evidence.

For required entries, every catalog case must be present. A case supplies a valid method and a nonempty `context` object containing `viewport`, `modality`, `state`. Viewport is a nonempty string or an object with finite positive numeric `width`/`height`; modality and state are nonempty strings. Extra context fields, such as browser/fixture, are permitted and participate in exact equality. Optional `measurement_ids` is a unique list of legacy measurement-check IDs. Select scenarios and contexts by the actual brief/rendering risks; there is no universal viewport matrix or numerical optical-center rule.

When `--previous` is used, its previously required commitments and cases must remain required with the same methods, contexts and measurement links. Contract `changes: {"requirement-id": "explicit supported brief/scope change reason"}` permits a documented change to that inherited item. A reason cannot waive currently required catalog items/cases or method coverage. The checker validates reason presence, not its authorization or correctness. A frozen first draft's omissions do not establish user approval.

## Observations and evidence

```json
{
  "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "results": [
    {
      "requirement_id": "control-feedback",
      "case_id": "pointer",
      "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "method": "browser",
      "context": {"viewport": "320x900", "modality": "pointer", "state": "closed"},
      "status": "pass",
      "evidence": ["pointer-events.json"],
      "finding": "Pointer action completed and trigger remained anchored."
    },
    {
      "requirement_id": "control-feedback",
      "case_id": "paint",
      "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "method": "rendered",
      "context": {"viewport": "320x900", "modality": "keyboard", "state": "focused"},
      "status": "pass",
      "evidence": ["keyboard-focus.png"],
      "finding": "Focus paint remains visible, unclipped and distinct from selection."
    }
  ],
  "measurements": {
    "status": "pass",
    "checks": [{"id": "trigger-stability", "status": "pass", "evidence": {"max_edge_delta_px": 0}}]
  }
}
```

Each required case needs exactly one result with exact source hash, method and context equality. Status is `pass`, `fail` or `incomplete`. `finding` is nonempty. `evidence` is a nonempty unique list of relative paths to existing nonempty files under the supplied evidence root. Absolute paths, parent traversal, missing/empty files and resolved symlinks escaping the root are incomplete. `rendered` additionally needs at least one `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` or `.avif` evidence file. A source file cannot discharge a rendered requirement.

Optional `measurements` embeds the unchanged legacy checker report (`status`, nonempty `checks` with unique IDs and statuses). Supplied report/check statuses must be valid and consistent. Preserve the original measurement result objects; the coverage validator does not recompute them. A case declaring `measurement_ids` requires the report, each named check, its valid status, and a pass. Missing report/check/status is incomplete. Any supplied failed/incomplete measurement blocks ready even if it has no case link. A legacy `promised:false` stability result retains its measurement pass but has `evidence.applicable: false`; linking it to a required coverage case produces incomplete, so it cannot waive that case.

## Evidence limits

The validator checks declared completeness, identity/context consistency and file availability. It cannot detect a fabricated observation, prove a screenshot's contents or capture completeness, establish that a browser/skill was used, or assess purpose, optical balance, choreography, accessibility or taste. A nonempty image extension is an availability check; it is not a rendered-quality judgment. Source hashes are claimed provenance unless the collector/parent independently verifies them.

Select and inspect the actual experience with supported input. Retain native controls, keyboard operation, visible focus and user-controlled forced colors. Defect acceptance, delivered rendered evidence, user taste approval and publication authorization remain separate. Here `ready` describes the declared acceptance contract only; it never authorizes a commit or asserts universal defect freedom, natural triggering, current runtime or cross-host parity.

The mutation suite covers omitted catalog items/cases/results, wrong method/context/build, missing/empty/escaping evidence, missing findings, fail with incomplete, invalid/duplicate/unknown IDs, feature applicability, optional nonselection, workflow capability coverage, inherited commitment changes, measurement link failures, planning classifications/unmeasured scaffolds and CLI exit codes. It writes isolated test directories with inherited permissions under the scripts folder and removes them; the symlink escape case skips when the OS denies symlink creation. Synthetic fixture passes prove this mechanism, not a real interface.

When changing this catalog or validator, also run `python -B scripts/check_regression_catalog.py` from the skill root. It exercises the actual catalog's classifications and every required suffix against omission, stale context/build, inherited changes and legitimate optional absence. Evidence metadata is mocked. It prints a summary and writes a detailed JSON only with `--output PATH`; neither proves a real UI passed. Ordinary product work runs its applicable contract rather than this full mechanism suite.
