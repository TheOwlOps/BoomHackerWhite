"""Tests for hard scope enforcement (strix/scope.py)."""

from typing import Any

import pytest

from strix import scope as scope_module
from strix.scope import Scope, check_tool_scope, extract_urls


SCAN_CONFIG: dict[str, Any] = {
    "targets": [
        {
            "type": "web_application",
            "details": {"target_url": "https://app.example.com"},
            "original": "https://app.example.com",
        },
        {
            "type": "ip_address",
            "details": {"target_ip": "10.0.0.5"},
            "original": "10.0.0.5",
        },
        {
            "type": "repository",
            "details": {"target_repo": "https://github.com/org/repo"},
            "original": "https://github.com/org/repo",
        },
    ]
}


class _FakeTracer:
    scan_config = SCAN_CONFIG


@pytest.fixture(autouse=True)
def _fake_tracer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("strix.telemetry.tracer.get_global_tracer", _FakeTracer)
    monkeypatch.delenv("BHW_DISABLE_SCOPE_ENFORCEMENT", raising=False)


def test_scope_allows_exact_host_and_subdomains() -> None:
    scope = Scope.from_scan_config(SCAN_CONFIG)
    assert scope is not None
    assert scope.allows_host("app.example.com")
    assert scope.allows_host("api.app.example.com")
    assert not scope.allows_host("example.com")
    assert not scope.allows_host("evil-example.com")
    assert not scope.allows_host("app.example.com.evil.com")


def test_scope_ip_targets_match_exactly() -> None:
    scope = Scope.from_scan_config(SCAN_CONFIG)
    assert scope is not None
    assert scope.allows_host("10.0.0.5")
    assert not scope.allows_host("10.0.0.6")


def test_repository_target_grants_no_network_hosts() -> None:
    scope = Scope.from_scan_config(SCAN_CONFIG)
    assert scope is not None
    assert not scope.allows_host("github.com")


def test_no_targets_means_unrestricted() -> None:
    assert Scope.from_scan_config(None) is None
    assert Scope.from_scan_config({}) is None
    assert Scope.from_scan_config({"targets": []}) is None


def test_check_blocks_out_of_scope_browser_navigation() -> None:
    error = check_tool_scope(
        "browser_action", {"action": "navigate", "url": "https://evil.com/phish"}
    )
    assert error is not None
    assert "evil.com" in error
    assert "app.example.com" in error


def test_check_allows_in_scope_terminal_command() -> None:
    error = check_tool_scope(
        "terminal_execute", {"command": "curl -s https://app.example.com/login"}
    )
    assert error is None


def test_check_blocks_out_of_scope_url_inside_python_code() -> None:
    error = check_tool_scope(
        "python_action",
        {"code": "import requests; requests.get('http://169.254.169.254/latest/meta-data')"},
    )
    assert error is not None
    assert "169.254.169.254" in error


def test_bookkeeping_tools_are_never_blocked() -> None:
    # Notes legitimately contain reference URLs to third-party sites.
    assert (
        check_tool_scope(
            "create_note",
            {"content": "See https://owasp.org/www-project-web-security-testing-guide/"},
        )
        is None
    )


def test_check_can_be_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BHW_DISABLE_SCOPE_ENFORCEMENT", "true")
    assert check_tool_scope("browser_action", {"url": "https://evil.com"}) is None


def test_extract_urls_recurses() -> None:
    args = {"a": ["x https://one.example.com/a", {"b": "http://two.example.com"}]}
    urls = extract_urls(args)
    assert "https://one.example.com/a" in urls
    assert "http://two.example.com" in urls


def test_scope_module_has_no_side_effects_on_import() -> None:
    assert scope_module.ENFORCED_TOOLS  # importable without a tracer present
