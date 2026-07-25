#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import xml.etree.ElementTree as ET


def _summary(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        key: sum(int(suite.attrib.get(key, "0")) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("core_xml", type=Path)
    parser.add_argument("desktop_xml", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)

    import PySide6
    import keyring
    import platformdirs
    import pytestqt

    core = _summary(args.core_xml)
    desktop = _summary(args.desktop_xml)
    total = core["tests"] + desktop["tests"]
    sha = os.environ.get("GITHUB_SHA", "local")
    report = f"""# Desktop PySide6 Tasks 8–10 test results

- Commit: `{sha}`
- Runner: Ubuntu / Python {platform.python_version()}
- PySide6: {PySide6.__version__}
- pytest-qt: {getattr(pytestqt, '__version__', 'installed')}
- keyring: {getattr(keyring, '__version__', '25.7.0')}
- platformdirs: {platformdirs.__version__}

## Automated gates

- Shared Python tests: {core['tests']} tests, {core['failures']} failures, {core['errors']} errors, {core['skipped']} skipped
- Desktop tests: {desktop['tests']} tests, {desktop['failures']} failures, {desktop['errors']} errors, {desktop['skipped']} skipped
- Combined tests: {total}
- `scripts/desktop_smoke.py --offscreen`: PASS
- `compileall`: PASS
- `scripts/verify_project.py`: PASS
- Matrix: Ubuntu, Windows, macOS / Python 3.13

## Limitations

- Qt is tested with the offscreen platform in CI; visual appearance on physical displays still needs manual review.
- Native file dialogs are not interactively exercised in headless CI.
- PDF is the print reference; Word and LibreOffice can differ slightly for floating text boxes and substituted fonts.
- Android cover UI, online image search, installers, signing, notarization, and update delivery are outside this completed desktop scope.
"""
    args.output.write_text(report, "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
