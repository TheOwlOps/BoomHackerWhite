"""Tests for SARIF + scan summary exports (strix/sarif.py)."""

from strix.sarif import build_sarif, build_scan_summary


REPORTS = [
    {
        "id": "vuln-0001",
        "title": "SQL Injection in /login",
        "severity": "critical",
        "description": "Login form is injectable",
        "impact": "Full database read",
        "target": "https://app.example.com/login",
        "endpoint": "/login",
        "method": "POST",
        "cwe": "CWE-89",
        "cvss": 9.8,
        "poc_script_code": "requests.post(...)",
        "fingerprint": "abc123",
        "code_locations": [
            {"file": "app/auth.py", "start_line": 42, "end_line": 45, "snippet": "query = ..."}
        ],
    },
    {
        "id": "vuln-0002",
        "title": "Missing security header",
        "severity": "low",
        "target": "https://app.example.com",
    },
]


def test_sarif_structure() -> None:
    sarif = build_sarif(REPORTS, tool_version="1.0.0")
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    driver = run["tool"]["driver"]
    assert driver["name"] == "BoomHackerWhite"
    assert driver["version"] == "1.0.0"
    assert len(run["results"]) == 2


def test_sarif_rule_ids_prefer_cwe() -> None:
    sarif = build_sarif(REPORTS)
    results = sarif["runs"][0]["results"]
    assert results[0]["ruleId"] == "CWE-89"
    assert results[1]["ruleId"] == "BHW-vuln-0002"


def test_sarif_levels_follow_severity() -> None:
    sarif = build_sarif(REPORTS)
    results = sarif["runs"][0]["results"]
    assert results[0]["level"] == "error"
    assert results[1]["level"] == "note"


def test_sarif_locations_use_code_locations() -> None:
    sarif = build_sarif(REPORTS)
    location = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "app/auth.py"
    assert location["region"]["startLine"] == 42


def test_sarif_carries_fingerprint_and_poc_flag() -> None:
    sarif = build_sarif(REPORTS)
    result = sarif["runs"][0]["results"][0]
    assert result["partialFingerprints"]["bhwFingerprint"] == "abc123"
    assert result["properties"]["hasProofOfConcept"] is True


def test_summary_counts() -> None:
    summary = build_scan_summary(REPORTS, duration_seconds=12.5, total_cost=0.42)
    assert summary["finding_count"] == 2
    assert summary["by_severity"] == {"critical": 1, "low": 1}
    assert summary["highest_severity"] == "critical"
    assert summary["duration_seconds"] == 12.5
    assert summary["total_cost_usd"] == 0.42


def test_empty_reports() -> None:
    sarif = build_sarif([])
    assert sarif["runs"][0]["results"] == []
    summary = build_scan_summary([])
    assert summary["finding_count"] == 0
    assert summary["highest_severity"] is None
