"""Tests for preflight diagnostics (strix/doctor.py)."""

import pytest

from strix import doctor


def _patch_all(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    defaults: dict[str, object] = {
        "check_python": lambda: doctor.Check("Python", doctor.OK, "3.12"),
        "check_docker_cli": lambda: doctor.Check("Docker CLI", doctor.OK, "found"),
        "check_docker_daemon": lambda: doctor.Check("Docker daemon", doctor.OK, "up"),
        "check_sandbox_image": lambda: doctor.Check("Sandbox image", doctor.OK, "pulled"),
        "check_llm": lambda: doctor.Check("LLM model", doctor.OK, "openai/gpt-5.4"),
        "check_output_dir": lambda: doctor.Check("Output directory", doctor.OK, "/tmp"),
    }
    defaults.update(overrides)
    monkeypatch.setattr(
        doctor,
        "ALL_CHECKS",
        (
            defaults["check_python"],
            defaults["check_docker_cli"],
            defaults["check_docker_daemon"],
            defaults["check_sandbox_image"],
            defaults["check_llm"],
            defaults["check_output_dir"],
        ),
    )


def test_doctor_passes_when_all_ok(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_all(monkeypatch)
    assert doctor.run_doctor() == 0
    out = capsys.readouterr().out
    assert "[ OK ]" in out
    assert "Everything needed is in place" in out


def test_doctor_fails_and_prints_fix(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_all(
        monkeypatch,
        check_llm=lambda: doctor.Check(
            "LLM model", doctor.FAIL, "STRIX_LLM is not set", "export STRIX_LLM=..."
        ),
    )
    assert doctor.run_doctor() == 1
    out = capsys.readouterr().out
    assert "[FAIL] LLM model" in out
    assert "export STRIX_LLM=..." in out


def test_doctor_warn_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_all(
        monkeypatch,
        check_sandbox_image=lambda: doctor.Check(
            "Sandbox image", doctor.WARN, "not pulled yet", "No action needed"
        ),
    )
    assert doctor.run_doctor() == 0


def test_llm_check_requires_key_for_hosted_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "strix.doctor.resolve_llm_config",
        lambda: ("openai/gpt-5.4", None, None),
    )
    result = doctor.check_llm()
    assert result.status == doctor.FAIL
    assert "LLM_API_KEY" in result.fix


def test_llm_check_ollama_needs_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "strix.doctor.resolve_llm_config",
        lambda: ("ollama/llama3", None, None),
    )
    assert doctor.check_llm().status == doctor.OK


def test_docker_cli_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    assert doctor.check_docker_cli().status == doctor.FAIL
    assert doctor.check_docker_daemon().status == doctor.FAIL
