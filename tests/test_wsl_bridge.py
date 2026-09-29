"""Exercise the WSL launcher with a stub in place of the Windows executable."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

WRAPPER = Path(__file__).resolve().parents[1] / "tools" / "paperflow-wsl"


@pytest.fixture(scope="module")
def wsl():
    executable = shutil.which("wsl.exe")
    if os.name != "nt" or not executable:
        pytest.skip("WSL integration test requires Windows with WSL")
    probe = subprocess.run([executable, "-e", "wslpath", "-u", "C:\\"], capture_output=True)
    if probe.returncode:
        pytest.skip("No working WSL distribution")
    return executable


def linux_path(wsl: str, path: Path) -> str:
    result = subprocess.run(
        [wsl, "-e", "wslpath", "-u", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def run_bridge(wsl: str, tmp_path: Path, args: list[str], cwd: Path | None = None, code=0):
    mock = tmp_path / "paperflow-mock"
    output = tmp_path / "args.txt"
    mock.write_bytes(
        b'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$BRIDGE_ARGS"\nexit "$BRIDGE_EXIT"\n'
    )
    command = [
        wsl,
        "-e",
        "env",
        f"PAPERFLOW_WINDOWS_EXE={linux_path(wsl, mock)}",
        f"BRIDGE_ARGS={linux_path(wsl, output)}",
        f"BRIDGE_EXIT={code}",
        "bash",
        linux_path(wsl, WRAPPER),
        *args,
    ]
    result = subprocess.run(
        command, cwd=cwd or tmp_path, capture_output=True, text=True, encoding="utf-8"
    )
    forwarded = output.read_text(encoding="utf-8").splitlines() if output.exists() else []
    return result, forwarded


def test_explicit_vault_paths_and_exit_status(wsl, tmp_path):
    vault = tmp_path / "研究 Vault"
    vault.mkdir()
    linux_vault = linux_path(wsl, vault)
    result, args = run_bridge(wsl, tmp_path, ["process", "key2026", "--vault", linux_vault], code=7)
    assert result.returncode == 7
    assert args == ["process", "key2026", "--vault", str(vault)]

    result, args = run_bridge(wsl, tmp_path, ["doctor", f"--vault={linux_vault}"])
    assert result.returncode == 0, result.stderr
    assert args == ["doctor", f"--vault={vault}"]


def test_vault_discovery_and_windows_path_passthrough(wsl, tmp_path):
    vault = tmp_path / "Vault with spaces"
    nested = vault / "02-Concepts"
    nested.mkdir(parents=True)
    (vault / ".paperflow").mkdir()
    (vault / ".paperflow" / "config.toml").write_text("", encoding="utf-8")

    result, args = run_bridge(wsl, tmp_path, ["sync"], cwd=nested)
    assert result.returncode == 0, result.stderr
    assert args == ["sync", "--vault", str(vault)]

    result, args = run_bridge(wsl, tmp_path, ["ingest", "key", "--vault", str(vault)])
    assert result.returncode == 0, result.stderr
    assert args == ["ingest", "key", "--vault", str(vault)]


def test_init_path_and_active_vault_fallback(wsl, tmp_path):
    result, args = run_bridge(wsl, tmp_path, ["init", "New Vault"])
    assert result.returncode == 0, result.stderr
    assert args == ["init", str(tmp_path / "New Vault")]

    result, args = run_bridge(wsl, tmp_path, ["doctor"])
    assert result.returncode == 0, result.stderr
    assert args == ["doctor"]


def test_rejects_linux_only_vault(wsl, tmp_path):
    result, args = run_bridge(wsl, tmp_path, ["init", "/home/example/Vault"])
    assert result.returncode == 2
    assert "Vault must be on a Windows drive" in result.stderr
    assert args == []

    result, args = run_bridge(wsl, tmp_path, ["doctor", "--vault", r"\\wsl.localhost\Ubuntu\home\Vault"])
    assert result.returncode == 2
    assert "Vault must be on a Windows drive" in result.stderr
    assert args == []
