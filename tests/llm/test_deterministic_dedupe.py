"""Tests for the deterministic dedupe fast path (strix/llm/dedupe.py)."""

from strix.llm.dedupe import deterministic_fingerprint, find_deterministic_duplicate


BASE = {
    "title": "SQL Injection in Login Form",
    "target": "https://app.example.com/login",
    "endpoint": "/login",
    "method": "POST",
    "cwe": "CWE-89",
}


def test_fingerprint_stable_under_cosmetic_changes() -> None:
    variant = {
        **BASE,
        "title": "sql injection in login form!",
        "target": "https://APP.example.com/login/",
    }
    assert deterministic_fingerprint(BASE) == deterministic_fingerprint(variant)


def test_fingerprint_differs_by_endpoint() -> None:
    other = {**BASE, "endpoint": "/search", "target": "https://app.example.com/search"}
    assert deterministic_fingerprint(BASE) != deterministic_fingerprint(other)


def test_fingerprint_differs_by_cwe() -> None:
    other = {**BASE, "cwe": "CWE-79"}
    assert deterministic_fingerprint(BASE) != deterministic_fingerprint(other)


def test_find_duplicate_matches_stored_fingerprint() -> None:
    existing = [{**BASE, "id": "vuln-0001", "fingerprint": deterministic_fingerprint(BASE)}]
    found = find_deterministic_duplicate(dict(BASE), existing)
    assert found is not None
    assert found["id"] == "vuln-0001"


def test_find_duplicate_computes_legacy_fingerprints() -> None:
    # Reports stored before fingerprints existed have no stored value; the
    # duplicate check must compute theirs on the fly.
    existing = [{**BASE, "id": "vuln-0007"}]
    found = find_deterministic_duplicate(dict(BASE), existing)
    assert found is not None
    assert found["id"] == "vuln-0007"


def test_no_false_positive_for_different_finding() -> None:
    existing = [{**BASE, "id": "vuln-0001"}]
    candidate = {**BASE, "title": "Stored XSS in profile page", "cwe": "CWE-79"}
    assert find_deterministic_duplicate(candidate, existing) is None
