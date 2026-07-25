from __future__ import annotations

import argparse
import json
from pathlib import Path


FORBIDDEN_DIRECTORY_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "python-tests",
    "desktop/tests",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}


def verify_portable(root: Path) -> dict[str, object]:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Portable directory not found: {root}")

    executable = root / "EPUB2A4.exe"
    internal = root / "_internal"
    if not executable.is_file():
        raise SystemExit(f"Missing executable: {executable}")
    if not internal.is_dir():
        raise SystemExit(f"Missing PyInstaller runtime directory: {internal}")

    files = [path for path in root.rglob("*") if path.is_file()]
    if not files:
        raise SystemExit("Portable directory contains no files.")

    qwindows = [path for path in files if path.name.lower() == "qwindows.dll"]
    if not qwindows:
        raise SystemExit("Missing Qt Windows platform plugin qwindows.dll.")

    forbidden: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        relative_text = relative.as_posix().lower()
        if path.is_dir() and (
            path.name in FORBIDDEN_DIRECTORY_NAMES
            or relative_text in FORBIDDEN_DIRECTORY_NAMES
        ):
            forbidden.append(relative.as_posix())
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            forbidden.append(relative.as_posix())
    if forbidden:
        raise SystemExit("Forbidden build artifacts found: " + ", ".join(sorted(forbidden)))

    total_bytes = sum(path.stat().st_size for path in files)
    if total_bytes <= 0:
        raise SystemExit("Portable directory has an invalid total size.")

    return {
        "root": str(root),
        "executable": str(executable),
        "qt_platform_plugin": str(qwindows[0]),
        "file_count": len(files),
        "total_bytes": total_bytes,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a PyInstaller Windows portable directory."
    )
    parser.add_argument("portable_dir", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = verify_portable(args.portable_dir)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
