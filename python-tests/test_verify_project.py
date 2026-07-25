from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_project_verifier_accepts_separate_desktop_package() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/verify_project.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
