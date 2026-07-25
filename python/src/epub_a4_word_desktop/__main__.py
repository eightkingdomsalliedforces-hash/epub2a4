from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="epub2a4-desktop")
    parser.add_argument("--legacy-gui", action="store_true")
    parser.add_argument("--portable-smoke-test", action="store_true", help=argparse.SUPPRESS)
    return parser


def run_qt_app(argv: list[str]) -> int:
    from .app import run

    return run(argv)


def run_portable_smoke(argv: list[str]) -> int:
    from .app import run_portable_smoke as run

    return run(argv)


def run_legacy_gui() -> int:
    from .legacy_gui import run

    return run()


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else None
    args, qt_args = build_parser().parse_known_args(raw_argv)
    if args.legacy_gui:
        return run_legacy_gui()
    if args.portable_smoke_test:
        return run_portable_smoke(qt_args)
    return run_qt_app(qt_args)


if __name__ == "__main__":
    raise SystemExit(main())
