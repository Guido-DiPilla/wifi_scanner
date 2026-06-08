#!/usr/bin/env python3
"""Automatically bump VERSION using commit-message heuristics.

Rules:
- major: if any commit message contains "BREAKING CHANGE" or uses Conventional Commits bang syntax.
- minor: otherwise.

Version format supports at least two numeric dot-separated segments.
For this repository's 4-part version scheme, major/minor reset lower segments to 0.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

AUTO_BUMP_PREFIX = "chore(version): auto-bump"


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout


def load_messages(ranges: list[str]) -> str:
    chunks: list[str] = []
    for item in ranges:
        if not item:
            continue
        if ".." in item:
            chunks.append(run_git(["log", "--format=%B", item]))
        else:
            chunks.append(run_git(["show", "-s", "--format=%B", item]))
    return "\n".join(chunks)


def decide_bump(messages: str) -> str:
    if re.search(r"(^|\n)BREAKING CHANGE:\s", messages):
        return "major"

    # Conventional Commits with breaking indicator, e.g. feat!: ..., refactor(api)!: ...
    if re.search(r"(^|\n)[a-zA-Z]+(?:\([^)]+\))?!:\s", messages):
        return "major"

    return "minor"


def parse_version(raw: str) -> list[int]:
    parts = raw.strip().split(".")
    if len(parts) < 2:
        raise ValueError("VERSION must contain at least major.minor")
    try:
        return [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError("VERSION segments must be integers") from exc


def bump(parts: list[int], bump_kind: str) -> list[int]:
    out = parts[:]
    if bump_kind == "major":
        out[0] += 1
        for i in range(1, len(out)):
            out[i] = 0
        return out

    if bump_kind == "minor":
        out[1] += 1
        for i in range(2, len(out)):
            out[i] = 0
        return out

    raise ValueError(f"Unsupported bump kind: {bump_kind}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-file", default="VERSION")
    parser.add_argument("--mode", choices=["auto", "major", "minor"], default="auto")
    parser.add_argument("--range", action="append", default=[])
    args = parser.parse_args()

    version_path = Path(args.version_file)
    if not version_path.exists():
        raise SystemExit(f"Version file not found: {version_path}")

    raw = version_path.read_text(encoding="utf-8").strip()
    parts = parse_version(raw)

    bump_kind = args.mode
    if bump_kind == "auto":
        messages = load_messages(args.range)
        bump_kind = decide_bump(messages)

    new_parts = bump(parts, bump_kind)
    new_version = ".".join(str(p) for p in new_parts)
    version_path.write_text(new_version + "\n", encoding="utf-8")

    print(f"bump_kind={bump_kind}")
    print(f"old_version={raw}")
    print(f"new_version={new_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
