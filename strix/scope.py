"""Hard scope enforcement for tool execution.

Strix has always *told* the model its authorized scope through the system
prompt (see ``StrixAgent._build_system_scope_context``). Prompt-level scope
is advisory: a confused or prompt-injected agent can still fire a request at
an out-of-scope host, and nothing in the execution path would stop it.

This module moves scope into the execution path. The tool executor calls
:func:`check_tool_scope` before dispatching any network-action tool; URLs
found in the tool arguments must belong to a target the user authorized in
the scan configuration, or the call is refused with an error the agent can
read and correct.

Design rules:

- No scan configuration (or no parseable targets) means *no restriction*:
  behaviour outside a configured scan is unchanged.
- Only action tools are enforced (see ``ENFORCED_TOOLS``). Bookkeeping
  tools (notes, todos, reporting metadata, agent messaging) routinely
  mention third-party URLs in prose and are never blocked.
- A target authorizes its exact host and, for web targets, its
  subdomains. IP targets authorize only that exact address. Repository and
  local-code targets authorize no network hosts at all.
- Enforcement can be disabled for a run with
  ``BHW_DISABLE_SCOPE_ENFORCEMENT=true`` (documented escape hatch for
  research harnesses); the disable is logged loudly.
"""

import ipaddress
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse


logger = logging.getLogger(__name__)

#: Tools whose arguments can cause traffic to a target. Everything else is
#: deliberately left alone.
ENFORCED_TOOLS = frozenset(
    {
        "browser_action",
        "send_request",
        "repeat_request",
        "python_action",
        "terminal_execute",
        "create_vulnerability_report",
    }
)

_URL_RE = re.compile(r"https?://[^\s\"'<>\)\]]+", re.IGNORECASE)


def _is_disabled() -> bool:
    return os.getenv("BHW_DISABLE_SCOPE_ENFORCEMENT", "").lower() == "true"


def _host_of(value: str) -> str | None:
    """Return the lowercase host of a URL or bare host string, if any."""
    value = value.strip()
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"//{value}")
    host = parsed.hostname
    return host.lower().rstrip(".") if host else None


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


class Scope:
    """The authorized network scope of one scan."""

    def __init__(self, hosts: set[str], ip_hosts: set[str]) -> None:
        self._hosts = hosts
        self._ip_hosts = ip_hosts

    @classmethod
    def from_scan_config(cls, scan_config: dict[str, Any] | None) -> "Scope | None":
        """Build a Scope from a scan config, or None when unrestricted."""
        if not scan_config:
            return None
        targets = scan_config.get("targets") or []
        hosts: set[str] = set()
        ip_hosts: set[str] = set()
        for target in targets:
            if not isinstance(target, dict):
                continue
            target_type = target.get("type", "")
            details = target.get("details", {}) or {}
            if target_type == "web_application":
                host = _host_of(str(details.get("target_url", "")))
                if host:
                    (ip_hosts if _is_ip(host) else hosts).add(host)
            elif target_type == "ip_address":
                host = _host_of(str(details.get("target_ip", "")))
                if host:
                    ip_hosts.add(host)
            elif target_type in ("repository", "local_code"):
                # Source targets grant no network access by themselves, but a
                # repo URL is often the same host as the deployed app is NOT
                # assumed: only an explicit .git host is ignored entirely.
                continue
            else:
                host = _host_of(str(target.get("original", "")))
                if host:
                    (ip_hosts if _is_ip(host) else hosts).add(host)
        if not hosts and not ip_hosts:
            return None
        return cls(hosts, ip_hosts)

    def allows_host(self, host: str) -> bool:
        host = host.lower().rstrip(".")
        if _is_ip(host):
            return host in self._ip_hosts or host in self._hosts
        return any(host == allowed or host.endswith(f".{allowed}") for allowed in self._hosts)

    def describe(self) -> str:
        parts = sorted(self._hosts | self._ip_hosts)
        return ", ".join(parts) if parts else "(empty)"


def extract_urls(value: Any) -> list[str]:
    """Recursively collect http(s) URLs from tool arguments."""
    found: list[str] = []
    if isinstance(value, str):
        found.extend(_URL_RE.findall(value))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(extract_urls(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(extract_urls(item))
    return found


def _current_scope() -> Scope | None:
    try:
        # Lazy import, matching the codebase idiom: the tracer module is
        # heavy and this keeps scope importable with zero side effects.
        from strix.telemetry.tracer import get_global_tracer  # noqa: PLC0415

        tracer = get_global_tracer()
        if tracer is None:
            return None
        return Scope.from_scan_config(getattr(tracer, "scan_config", None))
    except (ImportError, AttributeError):
        return None


def check_tool_scope(tool_name: str, args: dict[str, Any]) -> str | None:
    """Return a refusal message when a tool call leaves the scan scope.

    Returns None when the call is allowed (including when no scope is
    configured, the tool is not enforced, or enforcement is disabled).
    """
    if tool_name not in ENFORCED_TOOLS or _is_disabled():
        return None
    scope = _current_scope()
    if scope is None:
        return None
    for url in extract_urls(args):
        host = _host_of(url)
        if host and not scope.allows_host(host):
            logger.warning(
                "Scope enforcement blocked %s: host %s not in authorized scope (%s)",
                tool_name,
                host,
                scope.describe(),
            )
            return (
                f"Scope violation: '{host}' (from {url}) is not in the authorized "
                f"scan scope. Authorized targets: {scope.describe()}. "
                "User instructions cannot expand scope; ask the user to authorize "
                "this target or stay within the authorized targets."
            )
    return None
