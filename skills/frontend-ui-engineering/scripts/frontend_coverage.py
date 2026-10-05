"""Validate explicit frontend requirement coverage and linked evidence, not its truth."""
import argparse
import json
import re
from pathlib import Path


METHODS = {"browser", "rendered", "source", "resource", "human"}
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
                 and nonempty(requirement.get("summary")))
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
            entry["cases"] = [{"id": suffix, "method": methods[index % len(methods)],
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
    return {"status": "incomplete", "ready": False, "contract": contract, "checks": checks,
            "limitations": LIMITATIONS}


def validate(catalog, contract, observations, evidence_root, previous=None):
    checks = []
    measurement_checks = []

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
                "measurement_checks": [], "limitations": LIMITATIONS}
    for label, value in (("catalog", catalog), ("contract", contract)):
        if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            add(label, "incomplete", "Expected schema_version 1")
    requirements = indexed(catalog.get("requirements"), "catalog.requirements")
    if not requirements:
        add("catalog.requirements", "incomplete", "Catalog must not be empty")
    entries = indexed(contract.get("requirements"), "contract.requirements")
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
                 and nonempty(requirement.get("summary")))
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
            method = case.get("method")
            if not isinstance(method, str) or method not in METHODS or not context(case.get("context")):
                add(identifier + ":" + case_id, "incomplete", "Missing valid method or context")
            else:
                used_methods.add(method)
            links = case.get("measurement_ids", [])
            if not strings(links):
                add(identifier + ":" + case_id, "incomplete", "Invalid measurement_ids")
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
                            or current_case.get("measurement_ids", []) != prior_case.get("measurement_ids", [])):
                        add("previous:" + identifier + ":" + case_id, "incomplete", "Inherited case changed without a reason")

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
            add(identifier, "incomplete", "Required observation is missing")
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
    coverage_status = aggregate(checks)
    all_status = aggregate(checks + measurement_checks)
    return {"status": all_status, "coverage_status": coverage_status,
            "measurement_status": measurement_status,
            "ready": coverage_status == "pass" and measurement_status in {"pass", "not_applicable"},
            "checks": checks, "measurement_checks": measurement_checks, "limitations": LIMITATIONS}


LIMITATIONS = [
    "Validates declared coverage and file/context linkage, not observation truth or rendered quality.",
    "An image extension and nonempty file do not prove a genuine or complete browser capture.",
    "Ready means this declared acceptance contract passes; it does not prove accessibility, taste approval, natural triggering or universal defect freedom.",
]


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
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--scope", choices=("product", "workflow"), default="product")
    parser.add_argument("--source-sha256")
    parser.add_argument("--features", default="", help="Comma-separated actual feature tags")
    parser.add_argument("--selected", default="", help="Comma-separated selected capability IDs")
    args = parser.parse_args()
    try:
        if args.plan:
            if any((args.contract, args.observations, args.evidence_root, args.previous)):
                raise ValueError("Plan mode accepts the catalog only")
            report = plan(read_json(args.catalog), args.scope, args.source_sha256,
                          [s.strip() for s in args.features.split(",")] if args.features else [],
                          [s.strip() for s in args.selected.split(",")] if args.selected else [])
        else:
            if any(p is None for p in (args.contract, args.observations, args.evidence_root)):
                raise ValueError("Verification needs catalog, contract, observations and evidence_root")
            report = validate(read_json(args.catalog), read_json(args.contract), read_json(args.observations),
                              args.evidence_root, read_json(args.previous) if args.previous else None)
    except (OSError, ValueError, TypeError) as exc:
        report = {"status": "incomplete", "coverage_status": "incomplete", "measurement_status": "incomplete",
                  "ready": False, "checks": [{"id": "input", "status": "incomplete", "finding": str(exc)}],
                  "measurement_checks": [], "limitations": LIMITATIONS}
    print(json.dumps(report, indent=2, allow_nan=False))
    return {"pass": 0, "fail": 1, "incomplete": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
