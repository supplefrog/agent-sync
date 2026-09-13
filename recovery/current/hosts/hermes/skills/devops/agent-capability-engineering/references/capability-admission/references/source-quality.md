# Source quality for capability research

## Source order

For each material claim, prefer the closest authoritative artifact:

1. source code, specification, standard, API schema, dataset, or paper;
2. owner documentation, release notes, issue tracker, tests, benchmark method, or maintainer statement;
3. direct practitioner evidence with reproducible artifacts;
4. secondary analysis;
5. catalogs, snippets, social posts, newsletters, and videos.

Lower tiers are valuable for terminology and discovery. Follow their references upstream before relying on the claim. Many articles repeating one vendor post are one evidence lineage, not independent corroboration.

## Evidence labels

- **Documented:** an owner or specification states it.
- **Implemented:** current source contains the mechanism.
- **Verified:** a live or reproducible check observed it.
- **Inferred:** a conclusion drawn from the evidence.

Documentation can disagree with current source; source can differ from packaged runtime; a verified old model result can be irrelevant to a new model. State the strongest label actually supported.

## Search loop

1. Map decision-changing claim buckets and likely source owners.
2. Search a bounded set of independent source families.
3. Keep a ledger of query, URL, source tier, claim, version/date, and unresolved gap.
4. For every promising secondary source, trace upstream.
5. Search releases, history, tests, and issues when docs omit mechanism or failure modes.
6. Stop broadening when new searches no longer change the shortlist or decision.

Use popularity only as a lead or maintenance signal. Use old benchmarks as provenance, then test the current model and tool surface.

## Video-specific use

A video may reveal a useful capability, demo, vocabulary, or cited project. Extract the claim and references, then verify owner artifacts and current behavior. Do not force YouTube into research when a direct canonical source is available.
