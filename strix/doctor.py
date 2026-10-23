"""Preflight diagnostics: ``bhw --doctor``.

The most common failure mode for tools like this is "installed it, ran it,
nothing happened" — the process dies on a missing Docker daemon or an
unset LLM key, and the user never learns which prerequisite was missing.
The doctor checks every prerequisite up front, prints one line per check
with the exact fix for each failure, and exits non-zero when a scan could
not possibly run.

Run it any time with ``bhw --doctor`` (no target needed). The installer
scripts run it automatically at the end of installation.
"""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from strix.config.config import Config, resolve_llm_config


OK = "ok"
WARN = "warn"
FAIL = "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""


def check_python() -> Check:
    version = sys.version_info
    label = f"Python {version.major}.{version.minor}.{version.micro}"
    if version >= (3, 12):
        return Check("Python", OK, label)
    return Check("Python", FAIL, label, "Install Python 3.12 or newer.")


def check_docker_cli() -> Check:
    if shutil.which("docker"):
        return Check("Docker CLI", OK, "found in PATH")
    return Check(
        "Docker CLI",
        FAIL,
        "not found in PATH",
        "Install Docker Desktop (macOS/Windows) or Docker Engine (Linux), then re-run this check.",
    )


def _docker(args: list[str]) -> subprocess.CompletedProcess[str]:
    # Fixed argv, no shell: args come only from this module.
    return subprocess.run(  # noqa: S603
        ["docker", *args],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def check_docker_daemon() -> Check:
    if not shutil.which("docker"):
        return Check("Docker daemon", FAIL, "skipped (no Docker CLI)")
    try:
        result = _docker(["info", "--format", "{{.ServerVersion}}"])
    except (OSError, subprocess.TimeoutExpired):
        return Check(
            "Docker daemon",
            FAIL,
            "did not respond",
            "Start Docker and wait until it is fully up, then re-run.",
        )
    if result.returncode == 0:
        return Check("Docker daemon", OK, f"server {result.stdout.strip()}")
    return Check(
        "Docker daemon",
        FAIL,
        "not reachable",
        "Start Docker (on Linux: `sudo systemctl start docker`; make sure "
        "your user is in the `docker` group).",
    )


def check_sandbox_image() -> Check:
    image = Config.get("strix_image") or "ghcr.io/usestrix/strix-sandbox:0.1.13"
    if not shutil.which("docker"):
        return Check("Sandbox image", WARN, "skipped (no Docker CLI)")
    try:
        result = _docker(["image", "inspect", image])
    except (OSError, subprocess.TimeoutExpired):
        return Check("Sandbox image", WARN, "could not check")
    if result.returncode == 0:
        return Check("Sandbox image", OK, image)
    return Check(
        "Sandbox image",
        WARN,
        f"{image} not pulled yet",
        "No action needed: it downloads automatically on the first scan.",
    )


def check_llm() -> Check:
    model, api_key, _api_base = resolve_llm_config()
    if not model:
        return Check(
            "LLM model",
            FAIL,
            "STRIX_LLM is not set",
            "Set a model, e.g. `export STRIX_LLM='openai/gpt-5.4'` "
            "(or 'anthropic/claude-sonnet-4-6', 'ollama/llama3', ...).",
        )
    if model.startswith("ollama/") or "ollama" in model:
        return Check("LLM model", OK, f"{model} (local, no API key needed)")
    if not api_key:
        return Check(
            "LLM model",
            FAIL,
            f"{model} set, but no API key",
            "Set your key: `export LLM_API_KEY='sk-...'`.",
        )
    return Check("LLM model", OK, model)


def check_output_dir() -> Check:
    runs_dir = Path.cwd() / "strix_runs"
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        probe = runs_dir / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        return Check(
            "Output directory",
            FAIL,
            f"cannot write {runs_dir}: {e}",
            "Run from a directory you can write to.",
        )
    return Check("Output directory", OK, str(runs_dir))


ALL_CHECKS = (
    check_python,
    check_docker_cli,
    check_docker_daemon,
    check_sandbox_image,
    check_llm,
    check_output_dir,
)


def _say(text: str = "") -> None:
    sys.stdout.write(text + "\n")


def run_doctor() -> int:
    """Run all checks, print a report, return a process exit code."""
    _say("BoomHackerWhite doctor — checking whether a scan can run here\n")
    results: list[Check] = []
    for check_fn in ALL_CHECKS:
        try:
            results.append(check_fn())
        except Exception as e:  # noqa: BLE001
            results.append(Check(check_fn.__name__, FAIL, f"check crashed: {e}"))

    icons = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}
    for result in results:
        _say(f"{icons[result.status]} {result.name}: {result.detail}")
        if result.fix and result.status != OK:
            _say(f"         Fix: {result.fix}")

    failures = [r for r in results if r.status == FAIL]
    _say()
    if failures:
        _say(
            f"{len(failures)} blocking problem(s). Fix them, then run "
            "`bhw --doctor` again — after that, start a scan with e.g. "
            "`bhw -t https://your-app.example`."
        )
        return 1
    _say(
        "Everything needed is in place. Start a scan with "
        "`bhw -t https://your-app.example`, or try the bundled demo "
        "target in demo/ first."
    )
    return 0
