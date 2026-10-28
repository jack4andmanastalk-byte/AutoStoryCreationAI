#!/usr/bin/env python3
"""Check prospective run paths before relying on GitHub for persistence.

A passing check only means paths are eligible for versioning; it does not save,
commit, push, or check the contents for secrets, permissions, or size.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Arena snapshot exclusions are directory names, not just root-relative paths.
SNAPSHOT_EXCLUDED = frozenset({
    ".arena", ".cache", ".local", ".mypy_cache", ".next", ".nox", ".npm",
    ".nuxt", ".output", ".parcel-cache", ".playwright-cli", ".pytest_cache",
    ".ruff_cache", ".svelte-kit", ".tox", ".turbo", ".venv", ".vite",
    "__pycache__", "build", "coverage", "dist", "node_modules", "out", "target",
})


def check_path(root: Path, path: Path) -> str | None:
    root = root.resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return f"{path}: outside the repository"
    if not relative.parts:
        return f"{path}: choose a directory or file inside the repository"
    # Check both the requested and resolved names: a symlink must not hide an
    # excluded name or point outside the checkout.
    try:
        lexical = Path(path.absolute()).relative_to(root)
    except ValueError:
        return f"{path}: outside the repository"
    for part in (*lexical.parts, *relative.parts):
        if part == ".git" or part in SNAPSHOT_EXCLUDED:
            return f"{path}: excluded directory name {part!r}"
    # A sentinel makes directory ignore rules apply even when the directory does
    # not yet exist. Also check the path itself for file patterns.
    for candidate in (relative.as_posix(), (relative / ".persistence-probe").as_posix()):
        result = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--no-index", "-q", "--", candidate],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return f"{path}: ignored by Git ({candidate})"
        if result.returncode != 1:
            return f"{path}: git check-ignore failed: {result.stderr.strip()}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True)
    if result.returncode:
        print("error: run inside a Git repository", file=sys.stderr)
        return 2
    root = Path(result.stdout.strip())
    errors = [error for path in args.paths if (error := check_path(root, path))]
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    print("Paths are eligible for Git persistence; commit and push after reviewing contents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
