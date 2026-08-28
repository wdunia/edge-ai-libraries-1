#!/usr/bin/env python3
"""Demo-only build tweaks for the sample application Dockerfiles.

Backend Dockerfile:
  * ``poetry lock`` before install - the demo adds ``psutil`` to pyproject.toml
    (see patches/030-pyproject-psutil.patch) which invalidates the shipped lock
    file; regenerating it inside the image keeps the working copy clean.
  * ``curl gawk grep`` at runtime - required by the demo metrics collector.

UI Dockerfile:
  * ``npm ci`` falls back to ``npm install --no-package-lock`` because the demo
    adds chart/markdown dependencies that are not in the shipped package-lock.

All replacements are idempotent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def replace_once(content: str, old: str, new: str, label: str) -> str:
    if new in content:
        print(f"  = {label}: already applied")
        return content
    if old not in content:
        print(f"  ! {label}: anchor not found (upstream drift?)", file=sys.stderr)
        return content
    print(f"  + {label}")
    return content.replace(old, new, 1)


def patch_backend(path: Path) -> None:
    content = path.read_text(encoding="utf-8")

    content = replace_once(
        content,
        "RUN poetry config virtualenvs.create false && \\\n"
        "    poetry install --only main --no-root && \\\n"
        "    rm -rf ~/.cache",
        "RUN poetry config virtualenvs.create false && \\\n"
        "    poetry lock && \\\n"
        "    poetry install --only main --no-root && \\\n"
        "    rm -rf ~/.cache",
        "poetry lock before install",
    )

    content = replace_once(
        content,
        "    libjemalloc2 libpq5 && \\\n",
        "    libjemalloc2 libpq5 curl gawk grep && \\\n",
        "runtime tools for metrics collection",
    )

    path.write_text(content, encoding="utf-8")


def patch_ui(path: Path) -> None:
    content = path.read_text(encoding="utf-8")

    content = replace_once(
        content,
        'RUN ["npm", "ci"]',
        "RUN npm ci || npm install --no-package-lock",
        "npm ci fallback for demo dependencies",
    )

    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    patch_backend(work_dir / "Dockerfile")
    patch_ui(work_dir / "ui" / "react" / "Dockerfile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

