"""Validate explicit frontend requirement coverage and linked evidence, not its truth."""
import argparse
import hashlib
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote


METHODS = {"browser", "rendered", "source", "resource", "human"}
STAGES = {"pre_review", "human_choice", "integration", "publication"}
CLASSES = {"requirement", "capability", "conditional", "tentative", "project"}
STATUSES = {"pass", "fail", "incomplete"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return (isinstance(value, list) and all(nonempty(v) for v in value)
            and len(set(value)) == len(value))


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def evidence_file(root, relative, image=False):
    """Return only a nonempty, contained local file; never accept URLs or traversal."""
    if not nonempty(relative):
        return None
    path = Path(relative.replace("\\", "/"))
    try:
        target = (Path(root).resolve() / path).resolve()
        if (path.is_absolute() or ".." in path.parts or ":" in relative
                or not target.is_relative_to(Path(root).resolve()) or not target.is_file()
                or target.stat().st_size == 0 or (image and target.suffix.lower() not in IMAGE_EXTENSIONS)):
            return None
        return target
    except (OSError, ValueError):
        return None


def context(value):
    if not isinstance(value, dict) or not all(k in value for k in ("viewport", "modality", "state")):
        return False
    viewport = value["viewport"]
    viewport_ok = nonempty(viewport) or (isinstance(viewport, dict) and all(
        isinstance(viewport.get(k), (int, float)) and not isinstance(viewport[k], bool)
        and 0 < viewport[k] < float("inf") for k in ("width", "height")))
    return viewport_ok and nonempty(value["modality"]) and nonempty(value["state"])


def aggregate(checks):
    return "fail" if any(c["status"] == "fail" for c in checks) else (
        "incomplete" if any(c["status"] == "incomplete" for c in checks) else "pass")


def case_policy(requirement):
    """Only the catalog owns stage and per-case allowed-method constraints."""
    suffixes = requirement.get("cases", [])
    stages = requirement.get("case_stages", {})
    methods = requirement.get("case_methods", {})
    return (isinstance(stages, dict) and isinstance(methods, dict)
            and all(k in suffixes and isinstance(v, str) and v in STAGES for k, v in stages.items())
            and all(k in suffixes and strings(v) and bool(v)
                    and set(v) <= set(requirement.get("methods", [])) for k, v in methods.items()))


def deferred_context(value):
    # Only absent or untouched scaffold context is pending, never malformed filled data.
    return value is None or value == {"viewport": "", "modality": "", "state": ""}


def disposition(requirement, scope, features, selected):
    kind, tags = requirement["class"], requirement["features"]
    required = ((scope == "workflow" and kind in {"requirement", "capability", "conditional"})
                or (scope == "product" and kind in {"requirement", "conditional"}
                    and ("common" in tags or bool(set(tags) & set(features))))
                or (scope == "product" and kind == "capability" and requirement["id"] in selected))
    return "required" if required else (
        "tentative" if kind == "tentative" else "project" if kind == "project" else
        "unselected" if kind == "capability" else "not_applicable")


def plan(catalog, scope, source_sha256, features, selected):
    """Build an explicitly incomplete scaffold; never infer feature presence or observations."""
    checks = []

    def issue(identifier, finding):
        checks.append({"id": identifier, "status": "incomplete", "finding": finding})

    contract = {"schema_version": 1, "scope": scope, "source_sha256": source_sha256,
                "features": features, "selected": selected, "requirements": []}
    requirements = catalog.get("requirements") if isinstance(catalog, dict) else None
    if (not isinstance(catalog, dict) or type(catalog.get("schema_version")) is not int
            or catalog.get("schema_version") != 1 or not isinstance(requirements, list) or not requirements):
        issue("catalog", "Expected a nonempty schema_version 1 catalog")
        requirements = []
    if not isinstance(scope, str) or scope not in {"product", "workflow"}:
        issue("scope", "Expected product or workflow")
    if not sha(source_sha256):
        issue("source_sha256", "Expected 64 hexadecimal characters")
    for label, items in (("features", features), ("selected", selected)):
        if not strings(items):
            issue(label, "Expected unique nonempty strings")
    features = features if strings(features) else []
    selected = selected if strings(selected) else []
    known = {}
    tags = set()
    reasons = {"not_applicable": "No declared product feature matches; collector must verify feature absence.",
               "unselected": "Optional capability is not selected for this product.",
               "tentative": "Tentative observation remains a separate unresolved decision.",
               "project": "Project-specific decision is retained at its original scope."}
    for requirement in requirements:
        if not isinstance(requirement, dict) or not nonempty(requirement.get("id")):
            issue("catalog", "Missing catalog requirement identifier")
            continue
        identifier = requirement["id"]
        if identifier in known:
            issue(identifier, "Duplicate catalog identifier")
            continue
        kind = requirement.get("class")
        methods, cases, feature_tags = (requirement.get(k) for k in ("methods", "cases", "features"))
        valid = (isinstance(kind, str) and kind in CLASSES and strings(methods) and bool(methods)
                 and set(methods) <= METHODS and strings(cases) and bool(cases) and strings(feature_tags)
                 and nonempty(requirement.get("summary")) and case_policy(requirement))
        if not valid:
            issue(identifier, "Malformed catalog requirement")
            continue
        known[identifier] = requirement
        tags.update(feature_tags)
        classification = disposition(requirement, scope, features, selected)
        entry = {"id": identifier, "disposition": classification, "cases": []}
        if classification == "required":
            if len(methods) > len(cases):
                issue(identifier, "Catalog needs enough case suffixes to cover its evidence methods")
            entry["cases"] = [{"id": suffix, "method": requirement.get("case_methods", {}).get(suffix, [methods[index % len(methods)]])[0],
                               "context": {"viewport": "", "modality": "", "state": ""}}
                              for index, suffix in enumerate(cases)]
        else:
            entry["reason"] = reasons[classification]
        contract["requirements"].append(entry)
    for tag in set(features) - tags:
        issue("features:" + tag, "Unknown catalog feature tag")
    for identifier in selected:
        if identifier not in known or known[identifier]["class"] != "capability":
            issue("selected:" + identifier, "Selected IDs must name catalog capabilities")
    issue("unmeasured", "Scaffold only: verify features, fill actual contexts and collect linked observations/evidence")
    return {"status": "incomplete", "ready": False, "pre_review_status": "incomplete", "pre_review_ready": False,
            "pending_later_cases": [], "contract": contract, "checks": checks,
            "limitations": LIMITATIONS}


def validate(catalog, contract, observations, evidence_root, previous=None):
    checks = []
    measurement_checks = []
    pending_later_cases = []
    deferred_cases = {}

    def add(identifier, status, finding, **extra):
        checks.append({"id": identifier, "status": status, "finding": finding, **extra})

    def indexed(items, label, key="id"):
        output = {}
        if not isinstance(items, list):
            add(label, "incomplete", "Expected an array")
            return output
        for item in items:
            if not isinstance(item, dict) or not nonempty(item.get(key)):
                add(label, "incomplete", "Missing nonempty identifier")
            elif item[key] in output:
                add(label + ":" + item[key], "incomplete", "Duplicate identifier")
            else:
                output[item[key]] = item
        return output

    roots = (("catalog", catalog), ("contract", contract), ("observations", observations))
    for label, value in roots:
        if not isinstance(value, dict):
            add(label, "incomplete", "Expected an object")
    if any(not isinstance(v, dict) for _, v in roots):
        return {"status": "incomplete", "coverage_status": "incomplete",
                "measurement_status": "not_applicable", "ready": False, "checks": checks,
                "measurement_checks": [], "pre_review_status": "incomplete", "pre_review_ready": False,
                "pending_later_cases": [], "limitations": LIMITATIONS}
    for label, value in (("contract", contract), ("observations", observations)):
        if "stage" in value or "case_stages" in value:
            add(label, "incomplete", "Stages are catalog-owned")
    for label, value in (("catalog", catalog), ("contract", contract)):
        if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            add(label, "incomplete", "Expected schema_version 1")
    requirements = indexed(catalog.get("requirements"), "catalog.requirements")
    if not requirements:
        add("catalog.requirements", "incomplete", "Catalog must not be empty")
    entries = indexed(contract.get("requirements"), "contract.requirements")
    root = Path(evidence_root).resolve()
    references = indexed(contract.get("references", []), "contract.references")
    for identifier, reference in references.items():
        target = evidence_file(root, reference.get("evidence"), image=True)
        if not nonempty(reference.get("authority")) or not sha(reference.get("sha256")) or target is None:
            add("reference:" + identifier, "incomplete", "Reference needs authority, SHA256 and contained nonempty image evidence")
        elif hashlib.sha256(target.read_bytes()).hexdigest().lower() != reference["sha256"].lower():
            add("reference:" + identifier, "incomplete", "Approved reference hash is stale")
    scope = contract.get("scope")
    if not isinstance(scope, str) or scope not in {"product", "workflow"}:
        add("scope", "incomplete", "Expected product or workflow scope")
    features, selected = contract.get("features"), contract.get("selected")
    for label, values in (("features", features), ("selected", selected)):
        if not strings(values):
            add(label, "incomplete", "Expected unique nonempty strings")
    features = features if strings(features) else []
    selected = selected if strings(selected) else []
    known_tags = {tag for requirement in requirements.values()
                  if strings(requirement.get("features")) for tag in requirement["features"]}
    for tag in set(features) - known_tags:
        add("features:" + tag, "incomplete", "Unknown catalog feature tag")
    for identifier in selected:
        if identifier not in requirements or requirements[identifier].get("class") != "capability":
            add("selected:" + identifier, "incomplete", "Selected IDs must name catalog capabilities")
    expected_sha = contract.get("source_sha256")
    if not sha(expected_sha):
        add("source_sha256", "incomplete", "Expected a 64-character hexadecimal hash")
    if not sha(observations.get("source_sha256")) or observations.get("source_sha256") != expected_sha:
        add("observations.source_sha256", "incomplete", "Observation build must match contract")
    changes = contract.get("changes", {})
    if not isinstance(changes, dict):
        add("changes", "incomplete", "Expected requirement ID to nonempty reason mapping")
        changes = {}
    for identifier, reason in changes.items():
        if identifier not in requirements or not nonempty(reason):
            add("changes:" + str(identifier), "incomplete", "Unknown requirement or missing change reason")

    required_cases = {}
    for identifier, requirement in requirements.items():
        kind = requirement.get("class")
        tags, methods, suffixes = (requirement.get(k) for k in ("features", "methods", "cases"))
        valid = (isinstance(kind, str) and kind in CLASSES and strings(tags) and strings(methods) and bool(methods)
                 and set(methods) <= METHODS and strings(suffixes) and bool(suffixes)
                 and nonempty(requirement.get("summary")) and case_policy(requirement))
        if not valid:
            add(identifier, "incomplete", "Malformed catalog requirement")
            continue
        classification = disposition(requirement, scope, features, selected)
        applicable = classification == "required"
        entry = entries.get(identifier)
        if entry is None:
            add(identifier, "incomplete", "Catalog item is unclassified")
            continue
        if entry.get("disposition") != classification:
            add(identifier, "incomplete", "Disposition must be " + classification)
        if "case_stages" in entry or "stage" in entry:
            add(identifier, "incomplete", "Stages are catalog-owned; contract overrides are invalid")
        cases = indexed(entry.get("cases"), identifier + ".cases")
        if not applicable:
            if not nonempty(entry.get("reason")):
                add(identifier, "incomplete", "Non-required classification needs a reason")
            if cases:
                add(identifier, "incomplete", "Non-required entry must not declare acceptance cases")
            continue
        for suffix in suffixes:
            if suffix not in cases:
                add(identifier + ":" + suffix, "incomplete", "Required catalog case is missing")
        used_methods = set()
        for case_id, case in cases.items():
            if case_id not in suffixes:
                add(identifier + ":" + case_id, "incomplete", "Unknown catalog case")
            stage = requirement.get("case_stages", {}).get(case_id, "pre_review")
            allowed = requirement.get("case_methods", {}).get(case_id, methods)
            method = case.get("method")
            if "stage" in case or "case_stages" in case:
                add(identifier + ":" + case_id, "incomplete", "Stages are catalog-owned; contract overrides are invalid")
            valid_method = isinstance(method, str) and method in METHODS and method in allowed
            if not valid_method:
                add(identifier + ":" + case_id, "incomplete", "Missing or disallowed case method")
            else:
                used_methods.add(method)
            later = case_id in suffixes and stage != "pre_review" and valid_method
            if later:
                deferred_cases[(identifier, case_id)] = stage
            if not context(case.get("context")):
                add(identifier + ":" + case_id, "incomplete", "Missing valid context",
                    pending=later and deferred_context(case.get("context")))
            links = case.get("measurement_ids", [])
            if not strings(links):
                add(identifier + ":" + case_id, "incomplete", "Invalid measurement_ids")
            reference_ids, criteria = case.get("reference_ids", []), case.get("criteria", [])
            if "reference_ids" in case or "criteria" in case:
                if (method != "rendered" or not strings(reference_ids) or not reference_ids
                        or not strings(criteria) or not criteria):
                    add(identifier + ":" + case_id, "incomplete", "Reference-bound rendered case needs nonempty unique reference_ids and criteria")
                elif any(ref not in references for ref in reference_ids):
                    add(identifier + ":" + case_id, "incomplete", "Case names an unknown approved reference")
            required_cases[(identifier, case_id)] = case
        if not set(methods) <= used_methods:
            add(identifier + ":methods", "incomplete", "Required evidence methods are not covered")
    for identifier in entries.keys() - requirements.keys():
        add(identifier, "incomplete", "Unknown contract requirement")

    if previous is not None:
        if not isinstance(previous, dict) or type(previous.get("schema_version")) is not int or previous.get("schema_version") != 1:
            add("previous", "incomplete", "Malformed previous contract")
        else:
            prior_entries = indexed(previous.get("requirements"), "previous.requirements")
            for identifier, prior in prior_entries.items():
                if identifier not in requirements:
                    add("previous:" + identifier, "incomplete", "Unknown inherited requirement")
                if prior.get("disposition") != "required" or nonempty(changes.get(identifier)):
                    continue
                current = entries.get(identifier, {})
                if current.get("disposition") != "required":
                    add("previous:" + identifier, "incomplete", "Inherited required commitment was dropped")
                prior_cases = indexed(prior.get("cases"), "previous:" + identifier + ".cases")
                current_cases = indexed(current.get("cases"), "current:" + identifier + ".cases")
                for case_id, prior_case in prior_cases.items():
                    current_case = current_cases.get(case_id, {})
                    if (any(current_case.get(k) != prior_case.get(k) for k in ("method", "context"))
                            or any(current_case.get(k, []) != prior_case.get(k, []) for k in
                                   ("measurement_ids", "reference_ids", "criteria"))):
                        add("previous:" + identifier + ":" + case_id, "incomplete", "Inherited case changed without a reason")
                    prior_refs = prior_case.get("reference_ids", [])
                    if strings(prior_refs):
                        prior_reference_map = indexed(previous.get("references", []), "previous.references")
                        for ref in prior_refs:
                            if ref not in prior_reference_map or references.get(ref) != prior_reference_map.get(ref):
                                add("previous:" + identifier + ":" + case_id, "incomplete", "Inherited reference identity changed without a reason")

    report = observations.get("measurements")
    measurements = {}
    measurement_status = "not_applicable"
    if report is not None:
        if not isinstance(report, dict):
            measurement_checks.append({"id": "measurements", "status": "incomplete", "finding": "Expected measurement report"})
        else:
            before = len(checks)
            measurements = indexed(report.get("checks"), "measurements.checks")
            measurement_checks.extend(checks[before:])
            del checks[before:]
            if not measurements:
                measurement_checks.append({"id": "measurements", "status": "incomplete", "finding": "Measurement checks must not be empty"})
            for identifier, item in measurements.items():
                status = item.get("status")
                measurement_checks.append({"id": identifier, "status": status if isinstance(status, str) and status in STATUSES else "incomplete",
                                           "finding": "Legacy measurement result", "result": item})
            if not isinstance(report.get("status"), str) or report.get("status") not in STATUSES or report.get("status") != aggregate(measurement_checks):
                measurement_checks.append({"id": "measurements.status", "status": "incomplete", "finding": "Missing or inconsistent measurement status"})
            elif report["status"] != "pass":
                measurement_checks.append({"id": "measurements.status", "status": report["status"], "finding": "Legacy measurement report is not pass"})
        measurement_status = aggregate(measurement_checks)

    raw_results = observations.get("results")
    results = {}
    if not isinstance(raw_results, list):
        add("results", "incomplete", "Expected observation results array")
        raw_results = []
    for result in raw_results:
        if not isinstance(result, dict) or not all(nonempty(result.get(k)) for k in ("requirement_id", "case_id")):
            add("results", "incomplete", "Missing result identifiers")
            continue
        if "stage" in result or "case_stages" in result:
            add("results", "incomplete", "Observation stages are catalog-owned")
        key = (result["requirement_id"], result["case_id"])
        if key in results:
            add(":".join(key), "incomplete", "Duplicate observation result")
        else:
            results[key] = result
        if key not in required_cases:
            add(":".join(key), "incomplete", "Unknown or non-required result case")
    root = Path(evidence_root).resolve()
    for key, case in required_cases.items():
        identifier = ":".join(key)
        result = results.get(key)
        if result is None:
            stage = deferred_cases.get(key)
            pending = stage is not None and (context(case.get("context")) or deferred_context(case.get("context")))
            add(identifier, "incomplete", "Required observation is missing", pending=pending)
            if pending:
                pending_later_cases.append({"requirement_id": key[0], "case_id": key[1],
                                            "stage": stage, "method": case.get("method")})
            continue
        status = result.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            add(identifier, "incomplete", "Invalid observation status")
        elif status != "pass":
            add(identifier, status, result.get("finding", "Observed case did not pass"))
        for field, expected in (("source_sha256", expected_sha), ("method", case.get("method")), ("context", case.get("context"))):
            if result.get(field) != expected:
                add(identifier, "incomplete", "Observation " + field + " does not match contract")
        if not nonempty(result.get("finding")):
            add(identifier, "incomplete", "Observation needs a finding")
        paths = result.get("evidence")
        images = False
        if not strings(paths) or not paths:
            add(identifier, "incomplete", "Evidence needs unique relative file paths")
            paths = []
        for relative in paths:
            path = Path(relative)
            try:
                target = (root / path).resolve()
                valid = (not path.is_absolute() and ".." not in path.parts
                         and target.is_relative_to(root) and target.is_file() and target.stat().st_size > 0)
            except (OSError, ValueError):
                valid = False
            if not valid:
                add(identifier, "incomplete", "Missing, empty or escaping evidence file: " + relative)
            elif target.suffix.lower() in IMAGE_EXTENSIONS:
                images = True
        if case.get("method") == "rendered" and not images:
            add(identifier, "incomplete", "Rendered judgment needs a nonempty image evidence file")
        if "reference_ids" in case or "criteria" in case:
            comparison = result.get("comparison")
            if not isinstance(comparison, dict):
                add(identifier, "incomplete", "Reference-bound case needs a comparison")
            else:
                if comparison.get("reference_ids") != case.get("reference_ids"):
                    add(identifier, "incomplete", "Comparison reference_ids must exactly match the case")
                rendered = comparison.get("rendered_evidence")
                if not strings(rendered) or not rendered:
                    add(identifier, "incomplete", "Comparison needs unique rendered image evidence")
                else:
                    for relative in rendered:
                        if relative not in paths or evidence_file(root, relative, image=True) is None:
                            add(identifier, "incomplete", "Comparison render must be valid linked image evidence: " + relative)
                findings = indexed(comparison.get("criteria_findings"), identifier + ".criteria_findings", "criterion")
                expected = case.get("criteria", [])
                expected = expected if strings(expected) else []
                if set(findings) != set(expected):
                    add(identifier, "incomplete", "Comparison must cover exactly every named criterion")
                for criterion, item in findings.items():
                    verdict = item.get("status")
                    if not isinstance(verdict, str) or verdict not in STATUSES or not nonempty(item.get("finding")):
                        add(identifier + ":" + criterion, "incomplete", "Criterion needs a valid verdict and concrete finding")
                    else:
                        add(identifier + ":" + criterion, verdict, item["finding"])
        for link in case.get("measurement_ids", []) if strings(case.get("measurement_ids", [])) else []:
            measurement = measurements.get(link)
            if measurement is None or not isinstance(measurement.get("status"), str) or measurement.get("status") not in STATUSES:
                add(identifier, "incomplete", "Missing linked measurement/check/status: " + link)
            elif isinstance(measurement.get("evidence"), dict) and measurement["evidence"].get("applicable") is False:
                add(identifier, "incomplete", "A non-applicable measurement cannot discharge a required case: " + link)
            elif measurement["status"] != "pass":
                add(identifier, measurement["status"], "Linked measurement is not pass: " + link)
        if status == "pass":
            add(identifier, "pass", result.get("finding", ""), evidence=paths)
    observed_keys = set(results)
    for check in checks:
        if check.get("pending") and any(check["id"] == ":".join(key) for key in observed_keys):
            check["pending"] = False
    pre_review_status = aggregate([c for c in checks if not c.get("pending")] + measurement_checks)
    coverage_status = aggregate(checks)
    all_status = aggregate(checks + measurement_checks)
    return {"status": all_status, "coverage_status": coverage_status,
            "measurement_status": measurement_status,
            "pre_review_status": pre_review_status, "pre_review_ready": pre_review_status == "pass",
            "pending_later_cases": pending_later_cases,
            "ready": coverage_status == "pass" and measurement_status in {"pass", "not_applicable"},
            "checks": checks, "measurement_checks": measurement_checks, "limitations": LIMITATIONS}


LIMITATIONS = [
    "Validates declared coverage and file/context linkage, not observation truth or rendered quality.",
    "An image extension and nonempty file do not prove a genuine or complete browser capture.",
    "Ready means this declared acceptance contract passes; it does not prove accessibility, taste approval, natural triggering or universal defect freedom.",
]


def review_html(contract, observations, evidence_root, report, output_path):
    """A local inspection packet. Verdicts are declarations, never pixel verification."""
    def esc(value):
        return html.escape(str(value), quote=True)

    def picture(relative, label, expected_hash=None):
        target = evidence_file(evidence_root, relative, image=True)
        if target is None:
            return '<p>Incomplete image evidence: ' + esc(relative) + '</p>'
        if expected_hash is not None and (not sha(expected_hash) or
                hashlib.sha256(target.read_bytes()).hexdigest().lower() != expected_hash.lower()):
            return '<p>Incomplete: reference hash mismatch for ' + esc(relative) + '</p>'
        limitation = ''
        try:
            relative_url = os.path.relpath(target, Path(output_path).resolve().parent).replace('\\', '/')
            uri = esc(quote(relative_url, safe='/'))
        except ValueError:
            uri = esc(target.as_uri())
            limitation = '<p>Cross-drive image: this file URL may require opening the packet as a local file; an HTTP preview cannot load it.</p>'
        return limitation + '<figure><a href="' + uri + '"><img src="' + uri + '" alt="' + esc(label) + '"></a><figcaption>' + esc(label) + ': ' + esc(relative) + '</figcaption></figure>'

    contract = contract if isinstance(contract, dict) else {}
    observations = observations if isinstance(observations, dict) else {}
    references = {r['id']: r for r in contract.get('references', [])
                  if isinstance(r, dict) and nonempty(r.get('id'))} if isinstance(contract.get('references', []), list) else {}
    results = {(r.get('requirement_id'), r.get('case_id')): r for r in observations.get('results', [])
               if isinstance(r, dict) and nonempty(r.get('requirement_id')) and nonempty(r.get('case_id'))} if isinstance(observations.get('results', []), list) else {}
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Frontend reference inspection</title>',
             '<style>body{font:16px system-ui;margin:2rem;line-height:1.5} .pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem}img{max-width:100%;height:auto}figure{margin:0 0 1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:1px solid #888;padding:1rem 0}@media(max-width:700px){.pair{grid-template-columns:1fr}}</style>',
             '<h1>Frontend reference inspection</h1><p>Unverified declarations. Inspect the real captures in a browser; file availability and hashes do not prove pixel fidelity, reference quality or approval.</p>',
             '<p>Declared acceptance status: ' + esc(report['status']) + '; ready: ' + esc(report['ready']) + '</p>',
             '<p>Exact revision SHA256: ' + esc(contract.get('source_sha256')) + '</p>']
    entries = contract.get('requirements', [])
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        cases = entry.get('cases', [])
        for case in cases if isinstance(cases, list) else []:
            if not isinstance(case, dict) or not ('reference_ids' in case or 'criteria' in case):
                continue
            identifier = str(entry.get('id')) + ':' + str(case.get('id'))
            result = results.get((entry.get('id'), case.get('id')), {})
            comparison = result.get('comparison', {})
            comparison = comparison if isinstance(comparison, dict) else {}
            parts.extend(['<section><h2>' + esc(identifier) + '</h2><pre>Exact context: ' + esc(json.dumps(case.get('context'), ensure_ascii=False)) + '</pre>',
                          '<div class="pair"><div><h3>Approved reference declarations</h3>'])
            ids = case.get('reference_ids', [])
            for ref in ids if strings(ids) else []:
                reference = references.get(ref, {})
                parts.append('<p>' + esc(ref) + ' — authority: ' + esc(reference.get('authority')) + '</p>')
                parts.append(picture(reference.get('evidence'), ref, reference.get('sha256', '')))
            parts.append('</div><div><h3>Current render declarations</h3>')
            rendered = comparison.get('rendered_evidence', [])
            linked = result.get('evidence', [])
            for relative in rendered if strings(rendered) else []:
                parts.append(picture(relative, 'Current render') if strings(linked) and relative in linked else '<p>Incomplete: render is not linked observation evidence</p>')
            if not strings(rendered) or not rendered:
                parts.append('<p>Incomplete: no comparison render</p>')
            parts.append('</div></div><h3>Named criteria and declared verdicts</h3><pre>' + esc(json.dumps({'required_criteria': case.get('criteria'), 'comparison': comparison}, indent=2, ensure_ascii=False)) + '</pre></section>')
    parts.append('<details><summary>Complete validator report (coverage and measurement findings)</summary><pre>' + esc(json.dumps(report, indent=2, ensure_ascii=False)) + '</pre></details></html>')
    return '\n'.join(parts)


def read_json(path):
    def invalid_constant(value):
        raise ValueError("Invalid JSON numeric constant: " + value)
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=invalid_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("contract", type=Path, nargs="?")
    parser.add_argument("observations", type=Path, nargs="?")
    parser.add_argument("evidence_root", type=Path, nargs="?")
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--review-html", type=Path, help="Write a local reference/render inspection packet at this path only")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--scope", choices=("product", "workflow"), default="product")
    parser.add_argument("--source-sha256")
    parser.add_argument("--features", default="", help="Comma-separated actual feature tags")
    parser.add_argument("--selected", default="", help="Comma-separated selected capability IDs")
    args = parser.parse_args()
    contract, observations = {}, {}
    try:
        if args.plan:
            if any((args.contract, args.observations, args.evidence_root, args.previous, args.review_html)):
                raise ValueError("Plan mode accepts the catalog only")
            report = plan(read_json(args.catalog), args.scope, args.source_sha256,
                          [s.strip() for s in args.features.split(",")] if args.features else [],
                          [s.strip() for s in args.selected.split(",")] if args.selected else [])
        else:
            if any(p is None for p in (args.contract, args.observations, args.evidence_root)):
                raise ValueError("Verification needs catalog, contract, observations and evidence_root")
            contract, observations = read_json(args.contract), read_json(args.observations)
            report = validate(read_json(args.catalog), contract, observations,
                              args.evidence_root, read_json(args.previous) if args.previous else None)
    except (OSError, ValueError, TypeError) as exc:
        report = {"status": "incomplete", "coverage_status": "incomplete", "measurement_status": "incomplete",
                  "ready": False, "pre_review_status": "incomplete", "pre_review_ready": False,
                  "pending_later_cases": [], "checks": [{"id": "input", "status": "incomplete", "finding": str(exc)}],
                  "measurement_checks": [], "limitations": LIMITATIONS}
    if args.review_html and not args.plan:
        try:
            args.review_html.write_text(review_html(contract, observations, args.evidence_root, report, args.review_html), encoding="utf-8")
        except (OSError, ValueError, TypeError) as exc:
            report['checks'].append({'id': 'review-html', 'status': 'incomplete', 'finding': str(exc)})
            report['status'] = aggregate(report['checks'] + report['measurement_checks'])
            report['coverage_status'] = aggregate(report['checks'])
            report['ready'] = False
            report['pre_review_ready'] = False
            report['pre_review_status'] = report['status']
    print(json.dumps(report, indent=2, allow_nan=False))
    return {"pass": 0, "fail": 1, "incomplete": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
