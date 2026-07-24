#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def collect_mm_values(value: object, path: str = "$") -> dict[str, float]:
    found: dict[str, float] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key.endswith("_mm") and isinstance(child, (int, float)) and not isinstance(child, bool):
                found[child_path] = float(child)
            found.update(collect_mm_values(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(collect_mm_values(child, f"{path}[{index}]"))
    return found


def compare(left: dict[str, float], right: dict[str, float], tolerance: float) -> int:
    if tolerance < 0:
        print("tolerance must be non-negative")
        return 1
    if left.keys() != right.keys():
        missing = sorted(left.keys() ^ right.keys())
        print("Geometry keys differ:", ", ".join(missing))
        return 1
    deltas = {key: abs(left[key] - right[key]) for key in left}
    worst_path, worst_delta = max(
        deltas.items(), key=lambda item: item[1], default=("$", 0.0)
    )
    print(f"maximum delta={worst_delta:.6f} mm at {worst_path}")
    return 0 if worst_delta <= tolerance else 1


def _load(path: Path) -> dict[str, float]:
    payload: Any = json.loads(path.read_text("utf-8"))
    return collect_mm_values(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare all numeric JSON fields whose keys end in _mm."
    )
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--tolerance-mm", type=float, default=0.05)
    args = parser.parse_args(argv)
    return compare(_load(args.left), _load(args.right), args.tolerance_mm)


if __name__ == "__main__":
    raise SystemExit(main())
