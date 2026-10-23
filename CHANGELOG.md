# Changelog

All notable changes to BoomHackerWhite are documented here.

## 1.1.0 — Install & first-run experience

### Added

- **One-line installers** — `install.sh` (Linux/macOS) and `install.ps1`
  (Windows): install uv if needed, install BoomHackerWhite as an isolated
  tool (`bhw`, `boom-hacker-white`, `strix` commands), then run the
  doctor automatically.
- **`bhw --doctor`** — preflight diagnostics for the classic
  "installed it and nothing happens" failure: checks Python version,
  Docker CLI, Docker daemon, sandbox image, LLM model/API key and the
  output directory, prints the exact fix per failure, and exits non-zero
  while anything blocking is missing. No target required.
- **Bundled demo target** (`demo/vulnerable_target.py`) — a deliberately
  vulnerable, standard-library-only web app (SQL injection, reflected
  XSS, IDOR, command injection, path traversal) so a fresh install can
  prove itself end to end in minutes; see `demo/README.md`.

### Fixed

- `--doctor` (and `--version`) no longer require `--target`; argument
  parsing no longer crashes when no target is given in those modes.

## 1.0.0 — BoomHackerWhite (based on Strix 0.8.3)

First release of the BoomHackerWhite fork of [Strix](https://github.com/usestrix/strix)
(Apache-2.0), snapshot at upstream commit `15c9571`. The internal Python
package remains `strix` for compatibility; all `STRIX_*` environment
variables and the `strix` CLI keep working.

### Added

- **Hard scope enforcement** (`strix/scope.py`, wired into the tool
  executor): network-action tools (browser, proxy send/repeat, Python,
  terminal, vulnerability reporting) are refused when a URL in their
  arguments leaves the scan scope authorized in the scan configuration.
  Subdomains of an authorized web target are allowed; IP targets match
  exactly; repository/local-code targets grant no network hosts.
  Escape hatch: `BHW_DISABLE_SCOPE_ENFORCEMENT=true`.
- **SARIF 2.1.0 export** (`strix/sarif.py`): every run with findings also
  writes `findings.sarif.json` (for GitHub code scanning and CI security
  dashboards) and `scan-summary.json` (counts by severity, duration, cost).
- **Scan budget guard**: `BHW_MAX_SCAN_COST_USD` environment variable or
  `max_cost_usd` in the scan config. Agents receive a wrap-up warning at
  80% of the budget; the scan terminates after a five-iteration grace
  period past 100%, or immediately at 125%.
- **Agent graph persistence**: the multi-agent delegation graph is
  snapshotted atomically to `agents_graph.json` in the run directory when
  agents are created and when they finish, so a crash no longer loses the
  record of who was doing what.
- **CLI aliases**: `boom-hacker-white` and `bhw` entry points next to
  `strix`.

### Changed

- **Batched tool calls**: a single model response may now contain several
  independent tool calls. The streaming layer no longer truncates the
  response at the first `</function>`, the incomplete-call fixer closes
  any number of batched calls, and the system prompt instructs agents to
  batch independent work (never a finish tool, never dependent calls).
- **Deterministic dedupe fast path**: vulnerability reports are
  fingerprinted (normalized location + method + CWE + title tokens).
  Exact re-reports are rejected deterministically with confidence 1.0
  before the LLM dedupe judge runs, saving a model call per duplicate.
- **Memory compressor performance**: token counting is cached per
  (model, text), so compressing long histories no longer re-tokenizes
  every message on every iteration.
- Branding: CLI panels now read "BOOM HACKER WHITE"; package renamed to
  `boom-hacker-white`, version reset to `1.0.0`.

### Notes

- Upstream benchmark claims (XBEN) belong to upstream Strix releases and
  are not re-claimed for this fork; see `benchmarks/README.md`.
