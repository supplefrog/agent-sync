# Frontend coverage acceptance

Use `scripts/frontend_coverage.py` to check that a declared requirement catalog is completely classified and that required cases have linked evidence for the intended revision and context. This supplements `frontend_gate.py`; its four measurement checks and legacy CLI are unchanged. Coverage validation does not inspect a browser or determine whether observations are true.

Python 3.11+ standard library only. From the skill's scripts directory, using absolute input paths in project work:

```powershell
python -B frontend_coverage.py catalog.json contract.json observations.json evidence-directory --previous previous-contract.json
python -B frontend_coverage.py catalog.json contract.json observations.json evidence-directory --review-html review.html
python -B -m unittest -v test_frontend_coverage.py test_frontend_gate.py
```

`--previous` is optional. The CLI reads inputs and evidence metadata without modifying them. It emits JSON and exits `0` for pass, `1` for a retained failure, or `2` for incomplete inputs/coverage/evidence. A failure takes precedence over incomplete, retaining both kinds of finding. `coverage_status`, `measurement_status`, `checks`, `measurement_checks` and `ready` remain separate. `ready` is true only when applicable coverage passes and supplied/linked measurement checks pass. An absent measurement report is not applicable only when no case declares measurement links.

## Consume delivery at export and closeout

The additive delivery lane invokes `validate(catalog, contract, observations, evidence_root, previous)` on the supplied raw inputs. It ignores supplied coverage summaries. Legacy API/CLI calls above keep their semantics and schema version 1. Use the full owner catalog for whole-product delivery; keep transport/recovery separate from acceptance:

```powershell
python -B frontend_coverage.py catalog.json contract.json observations.json evidence-directory --delivery delivery.json --source-sha256 CURRENT64HEXSOURCEHASH --previous previous-contract.json --previous-delivery previous-delivery.json
python -B -m unittest -v test_frontend_delivery.py test_frontend_coverage.py test_frontend_gate.py
```

The project consumer resolves the trusted owner catalog and rejects supplied catalogs that omit or change its requirements, classifications, cases, stages or methods; additive project requirements remain valid. The parent independently verifies the actual source identity supplied with `--source-sha256`; all current records must match it. Both previous inputs are optional for a first delivery; retain them on revisions so inherited commitments and raw user/reviewer findings cannot silently disappear. The Python API is `delivery_acceptance(catalog, contract, observations, evidence_root, delivery, current_source_sha256, previous=None, previous_delivery=None)`. Generate `--review-html` separately with the legacy lane before consumption.

Merge `acceptance_extent` and the compact job mapping into the existing contract, alongside its current cases:

```json
{
  "acceptance_extent": "whole_product",
  "journeys": [{"id": "read-chapter", "job": "Read the selected chapter", "path": "/reader > chapter picker at reading position", "state_producer": "Chapter selection, restored location and browser history", "case_ids": ["I05:full-index-use-position", "I05:destination-agreement"]}]
}
```

Use actual existing case IDs. Derive necessary jobs and consequential state edges from the brief and inspected routes, controls and external state producers before acceptance, rather than converting only reported complaints into tests. The fresh reviewer explores the running product and discovers omitted paths; the typed mapping checks links, not completeness of that discovery. Each journey needs a nonempty job, actual access path and state producer, unique existing required `case_ids`, and at least one browser case. No fixed combination or journey count is imposed. On revision, changing an inherited journey needs the affected requirements' existing `changes` reasons.

Delivery receipt shape (merge real linked files and current identity):

```json
{
  "schema_version": 1,
  "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "extent": "whole_product",
  "known_findings": {"source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "findings": []},
  "scrutiny": {
    "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "extent": "whole_product", "status": "pass",
    "fresh_context": true, "read_only": true, "artifact_first": true, "ordinary_input": true,
    "explored_journey_ids": ["read-chapter"], "evidence": ["runtime-review.md", "chapter.png"],
    "finding": "Concrete current findings from ordinary running-product exploration, including omitted-path inspection."
  },
  "journey_results": [{
    "id": "read-chapter", "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "status": "pass", "context": {"viewport": "390x844", "modality": "touch", "state": "Mid-chapter reading position"},
    "finding": "Selection exposed the destination and retained coherent location feedback.",
    "steps": [
      {"at_ms": 0, "state": "Chapter one", "action": "Open chapter picker", "visible_result": "Choices visible at use position", "evidence": ["chapter.png"]},
      {"at_ms": 900, "state": "Chapter two", "action": "Select chapter two", "visible_result": "Destination and current indication agree", "evidence": ["chapter-events.json"]}
    ]
  }]
}
```

Every mapped journey needs exactly one current result, valid runtime context, status and concrete finding. Ordered steps link contained nonempty evidence from entry through the visible outcome; at least two steps with strictly increasing finite nonnegative `at_ms` are necessary for temporal linkage. Include intermediate, repeat, interruption or external-entry states where the actual state edges require them; this is not a new universal matrix. Repeat controls using existing `stable_control` and browser `scrollY` measurements when applicable. The validator checks evidence availability and declared chronology, not what the recording proves.

The current ledger is mandatory, including an explicit empty `findings` array when nothing remains. Entries have unique `id`, `kind` (`defect`, `unresolved`, `taste`), `status` (`open`, `resolved`), concrete `finding`, unique `case_ids` naming exact current required catalog cases and raw `evidence`. Unknown or non-required links block acceptance before any scope exclusion. Resolved in-scope entries also need current `resolution_evidence`; closure cannot erase the original finding/evidence. `--previous-delivery` requires retaining prior ID, kind, finding, case links and raw evidence. Open defects fail; open unresolved findings are incomplete. Taste stays distinct from defect acceptance and later human choice.

Whole-product acceptance requires matching `whole_product` in the contract and delivery, passing current applicable pre-review coverage, all mapped journeys, a current ledger with no open defect/unresolved finding, and passing source-bound scrutiny with all four controls true, concrete finding, linked evidence and exactly all mapped journey IDs explored. A narrow repair receipt cannot substitute for that scrutiny. Fresh context and artifact-first declarations must be verified under the standing dispatch contract; the consumer cannot establish their truth.

For an honest small repair, set both extents to `bounded_repair` and provide delivery `repair_case_ids` naming the affected current required pre-review cases. Keep the full validation report: acceptance considers affected case findings plus all global contract/integrity and measurement checks; unrelated case gaps stay visible. The consumer requests validator `include_check_scope=True`: typed `check_scope` identifies case-level verdict/evidence gaps and integrity errors. Duplicate/unknown observation IDs, malformed records, identity mismatches and escaping evidence remain integrity blockers regardless of textual ID prefixes; legacy validation omits this metadata by default. Scope the job map to affected behavior; a noninteractive repair can retain `journeys: []` and `journey_results: []`. Unmapped defects cannot be excluded, and intersecting open findings block repair closure. Small repairs require no compulsory reviewer; set `scrutiny_required: true` when the existing scrutiny trigger applies. Supplied scrutiny is checked even when optional. A bounded repair can only derive `repair_verified`, never whole-product readiness.

Output includes the recomputed `coverage` report, consumer `checks`, `status`, `acceptance`, `transport_allowed: true`, and `delivery_status`: `transported`, `repair_verified`, `ready_for_taste`, or `fully_ready`. Failed/incomplete acceptance preserves transport with acceptance false. CLI exits describe acceptance (`0` pass, `1` fail, `2` incomplete), not permission to export; callers must preserve recovery/export on nonzero exit. `ready_for_taste` requires whole-product acceptance; `fully_ready` additionally requires the full coverage report's `ready`, so deferred catalog stages remain pending. Neither status authorizes publication, replaces human approval or asserts defect freedom. Missing/unreadable delivery inputs also retain transport with acceptance false.

These fields prevent stale, narrow and failed receipts from being promoted by downstream delivery consumers. They cannot certify the running product, detect fabricated observations, prove complete feature/job inventory or turn synthetic probes into generation-quality evidence.

## Plan without rewriting classifications

```powershell
python -B frontend_coverage.py --plan --scope product --source-sha256 ACTUAL64HEXSOURCEHASH --features reader,chapter-reader --selected I21 ../references/regression-catalog.json
```

Plan mode takes only the catalog. Features and selected capability IDs are comma-separated lists; an omitted list is empty. It returns `{status: "incomplete", ready: false, contract: {...}, checks: [...]}` and exit `2`. Use the returned `contract` as a scaffold in the existing acceptance record. Classifications/reasons are inferred from the catalog and supplied feature inventory. Every required suffix is retained, methods use catalog per-case constraints or cyclic defaults to cover the catalog methods, and viewport/modality/state are intentionally empty. Rows with too few case suffixes to cover their methods are reported as unplannable rather than inventing IDs. Unknown feature tags, unknown/non-capability selections, duplicates and malformed catalogs are incomplete.

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

### Stages and per-case methods

Optional catalog `case_stages` maps existing suffixes to `pre_review`, `human_choice`, `integration` or `publication`; omitted suffixes default to `pre_review`. Optional `case_methods` maps existing suffixes to nonempty unique allowed-method lists drawn from the row's `methods`. Planning respects these constraints. Unknown suffixes/stages, malformed mappings and disallowed methods are incomplete. Contracts and observations cannot set stages.

The full `status`, `ready` and CLI exit codes retain their existing meanings. Separate `pre_review_status` and `pre_review_ready` describe defect readiness for the delivered proposal; `pending_later_cases` lists required later suffixes with no observation. Every suffix must still be declared with its valid method. Only missing observation and absent/untouched scaffold context for an exactly catalog-owned later suffix can be pending. Malformed filled context, supplied failed/incomplete/stale observations, missing previews/resource checks, invalid catalogs and inherited dropped/changed commitments still block pre-review. A supplied observation must meet all ordinary evidence checks even for a later case. Human/resource methods alone never exempt a case. Later approval is recorded with its actual allowed receipt method; an image cannot stand in for human selection. Deferred obligations block full ready until collected, and pre-review readiness grants no integration or publication authority.

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

### Approved reference commitments

When a rendered case must preserve an approved visual reference, bind that reference and name its perceptual commitments in the existing contract. These optional fields retain schema version 1 and leave cases without a reference unchanged. They do not require images, 3D, GPU rendering, centering or a new viewport matrix in products that do not select them.

Contract additions (merge into the existing contract and affected rendered case):

```json
{
  "references": [{"id": "approved-master", "evidence": "approved.png", "sha256": "ACTUAL64HEXSHA256OFFILE", "authority": "User-selected master"}],
  "reference_ids": ["approved-master"],
  "criteria": ["Composition", "Type hierarchy"]
}
```

`references` is a contract-level array of unique nonempty IDs. Each reference needs a nonempty authority receipt description, an actual 64-hex SHA256 of its nonempty image file, and an evidence-root-relative path. `reference_ids` and `criteria` belong on each affected rendered case, with nonempty unique strings. Each reference ID must exist. Use concrete named perceptual commitments from the approved treatment; the schema imposes no universal style rubric. The checker verifies file bytes against reference hashes, not approval authority or reference quality.

That case's observation adds:

```json
{
  "comparison": {
    "reference_ids": ["approved-master"],
    "rendered_evidence": ["current.png"],
    "criteria_findings": [
      {"criterion": "Composition", "status": "pass", "finding": "Describe the inspected spatial relationship and any difference."},
      {"criterion": "Type hierarchy", "status": "incomplete", "finding": "State what still needs real capture inspection."}
    ]
  }
}
```

Comparison reference IDs must exactly match the case list. Rendered evidence is a nonempty unique list of contained image files also present in that result's ordinary `evidence`. Every declared criterion needs exactly one finding with `pass`, `fail` or `incomplete` and a nonempty concrete explanation. Missing comparison, missing/extra criterion, mismatched reference, missing/escaping image or stale approved-reference hash blocks readiness. A failed criterion produces failure even when the result itself says pass; existing measurement and other coverage findings remain visible. With `--previous`, affected case reference IDs, criteria and each referenced identity (including file/hash/authority) cannot be changed or dropped without the existing requirement-level supported `changes` reason.

`--review-html PATH` writes only that requested file; its parent directory must already exist. It shows locally linked reference/render images side by side, exact case context and source revision, declared criterion verdicts, and the complete validator report. All supplied strings are HTML-escaped; links resolve only to validated contained local images, and a stale reference is labeled incomplete. Same-drive image URLs are relative to the output directory with URL-quoted forward-slash paths, supporting local-file viewing and HTTP previews that serve the packet and evidence under a common root. Cross-drive images fall back to file URLs with an explicit warning that HTTP previews cannot load them. The packet is labeled unverified even when declared acceptance passes. Open the HTML in a browser and inspect the real captures; metadata, file availability and human-written verdicts never prove pixels or reference quality. Generation does not relax CLI exit codes or hide incomplete measurements; write errors block readiness and retain existing failures. Plan mode cannot generate a review packet.

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
