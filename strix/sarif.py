"""SARIF 2.1.0 export for scan findings.

BoomHackerWhite writes human reports (Markdown/CSV) for every run. SARIF is
the machine-readable counterpart: GitHub code scanning, Azure DevOps and
most CI security dashboards ingest it natively, so findings can gate pull
requests and show up next to the code they affect without custom glue.

The conversion is a pure function over the stored report dicts so it can be
unit-tested without a tracer, a scan, or a network.
"""

from typing import Any


SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

_SEVERITY_TO_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
    "informational": "note",
}

_SEVERITY_TO_PRECISION = {
    "critical": "high",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "low",
}


def _rule_id(report: dict[str, Any]) -> str:
    cwe = str(report.get("cwe") or "").strip()
    if cwe:
        return cwe.upper()
    cve = str(report.get("cve") or "").strip()
    if cve:
        return cve.upper()
    return f"BHW-{report.get('id', 'finding')}"


def _locations(report: dict[str, Any]) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    for loc in report.get("code_locations") or []:
        artifact = str(loc.get("file") or "")
        if not artifact:
            continue
        region: dict[str, Any] = {}
        if isinstance(loc.get("start_line"), int):
            region["startLine"] = loc["start_line"]
        if isinstance(loc.get("end_line"), int):
            region["endLine"] = loc["end_line"]
        if loc.get("snippet"):
            region["snippet"] = {"text": str(loc["snippet"])}
        physical: dict[str, Any] = {"artifactLocation": {"uri": artifact}}
        if region:
            physical["region"] = region
        locations.append({"physicalLocation": physical})
    if not locations:
        target = str(report.get("endpoint") or report.get("target") or "")
        if target:
            locations.append({"physicalLocation": {"artifactLocation": {"uri": target}}})
    return locations


def build_sarif(reports: list[dict[str, Any]], tool_version: str = "") -> dict[str, Any]:
    """Convert stored vulnerability reports into a SARIF log dict."""
    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for report in reports:
        rule_id = _rule_id(report)
        severity = str(report.get("severity") or "medium").lower()
        if rule_id not in rules:
            rule: dict[str, Any] = {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": str(report.get("title") or rule_id)},
                "fullDescription": {
                    "text": str(report.get("description") or report.get("title") or rule_id)
                },
                "defaultConfiguration": {"level": _SEVERITY_TO_LEVEL.get(severity, "warning")},
                "properties": {"precision": _SEVERITY_TO_PRECISION.get(severity, "medium")},
            }
            if report.get("cwe"):
                rule["help"] = {
                    "text": f"See {report['cwe']} and the full Markdown report for remediation."
                }
            rules[rule_id] = rule

        message = str(report.get("title") or "Security finding")
        if report.get("impact"):
            message = f"{message} — Impact: {report['impact']}"
        result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": _SEVERITY_TO_LEVEL.get(severity, "warning"),
            "message": {"text": message},
            "locations": _locations(report),
            "partialFingerprints": {},
            "properties": {
                "reportId": report.get("id"),
                "severity": severity,
                "cvss": report.get("cvss"),
                "target": report.get("target"),
            },
        }
        if report.get("fingerprint"):
            result["partialFingerprints"]["bhwFingerprint"] = str(report["fingerprint"])
        if report.get("poc_script_code"):
            result["properties"]["hasProofOfConcept"] = True
        results.append(result)

    tool: dict[str, Any] = {"name": "BoomHackerWhite", "rules": list(rules.values())}
    if tool_version:
        tool["version"] = tool_version

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {"driver": tool},
                "results": results,
            }
        ],
    }


def build_scan_summary(
    reports: list[dict[str, Any]],
    duration_seconds: float | None = None,
    total_cost: float | None = None,
) -> dict[str, Any]:
    """Small machine-readable summary for CI gates and dashboards."""
    by_severity: dict[str, int] = {}
    for report in reports:
        severity = str(report.get("severity") or "unknown").lower()
        by_severity[severity] = by_severity.get(severity, 0) + 1
    summary: dict[str, Any] = {
        "tool": "BoomHackerWhite",
        "finding_count": len(reports),
        "by_severity": by_severity,
        "highest_severity": None,
    }
    for level in ("critical", "high", "medium", "low", "info"):
        if by_severity.get(level):
            summary["highest_severity"] = level
            break
    if duration_seconds is not None:
        summary["duration_seconds"] = duration_seconds
    if total_cost is not None:
        summary["total_cost_usd"] = total_cost
    return summary
