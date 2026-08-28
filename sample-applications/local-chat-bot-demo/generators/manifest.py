#!/usr/bin/env python3
"""Baseline drift detection for overlay files.

The demo replaces a handful of sample-application files with full copies
(``overlay/``).  Full-file replacement is convenient but silently discards
upstream changes, so every overlay target is fingerprinted against the
baseline revision.  When the fingerprint of the freshly prepared working copy
differs from the recorded one, the overlay file has to be refreshed.

Usage:
    manifest.py write --overlay <dir> --root <pristine-work-dir> --out <file>
    manifest.py check --overlay <dir> --root <pristine-work-dir> --file <file> [--strict]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ABSENT = "absent"


def normalized_digest(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def overlay_files(overlay_dir: Path) -> list[str]:
    files = [
        p.relative_to(overlay_dir).as_posix()
        for p in overlay_dir.rglob("*")
        if p.is_file() and p.name != "MANIFEST.sha256"
    ]
    return sorted(files)


def fingerprint(root: Path, rel: str) -> str:
    target = root / rel
    return normalized_digest(target) if target.is_file() else ABSENT


def cmd_write(args: argparse.Namespace) -> int:
    overlay_dir = Path(args.overlay)
    root = Path(args.root)
    lines = [
        "# sha256 (LF-normalized) of the BASELINE version of every overlay target.",
        "# 'absent' means the file does not exist upstream (demo-only file).",
        "# Regenerate with: scripts/make_patches.sh --refresh-manifest",
    ]
    for rel in overlay_files(overlay_dir):
        lines.append(f"{fingerprint(root, rel)}  {rel}")
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote manifest with {len(lines) - 3} entries to {args.out}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    overlay_dir = Path(args.overlay)
    root = Path(args.root)
    manifest_path = Path(args.file)

    if not manifest_path.is_file():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    recorded: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, rel = line.split("  ", 1)
        recorded[rel] = digest

    drifted: list[str] = []
    unknown: list[str] = []

    for rel in overlay_files(overlay_dir):
        if rel not in recorded:
            unknown.append(rel)
            continue
        if fingerprint(root, rel) != recorded[rel]:
            drifted.append(rel)

    for rel in unknown:
        print(f"WARNING: overlay file not present in manifest: {rel}", file=sys.stderr)

    if drifted:
        print("", file=sys.stderr)
        print("WARNING: upstream changed files that the demo overlays:", file=sys.stderr)
        for rel in drifted:
            print(f"  - {rel}", file=sys.stderr)
        print(
            "Refresh the overlay copies, then run "
            "scripts/make_patches.sh --refresh-manifest",
            file=sys.stderr,
        )
        if args.strict:
            return 1
    else:
        print("Overlay baseline check: OK")

    return 1 if (unknown and args.strict) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    writer = sub.add_parser("write")
    writer.add_argument("--overlay", required=True)
    writer.add_argument("--root", required=True)
    writer.add_argument("--out", required=True)
    writer.set_defaults(func=cmd_write)

    checker = sub.add_parser("check")
    checker.add_argument("--overlay", required=True)
    checker.add_argument("--root", required=True)
    checker.add_argument("--file", required=True)
    checker.add_argument("--strict", action="store_true")
    checker.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

