#!/usr/bin/env python3
"""Demo-only UI configuration for the working copy.

Vite inlines ``import.meta.env`` values at build time, therefore the demo
values must be present in ``ui/react/.env`` *before* the UI image is built and
the matching exports must exist in ``ui/react/src/config.ts``.

Both files are updated idempotently, existing keys are overwritten in place.
"""

from __future__ import annotations

import argparse
from pathlib import Path

METRICS_BLOCK = (
    "export const METRICS_URL: string =\n"
    "  import.meta.env.VITE_BACKEND_SERVICE_ENDPOINT + '/metrics';\n"
)
SYSTEM_INFO_BLOCK = (
    "export const SYSTEM_INFO: string =\n"
    "  import.meta.env.VITE_SYSTEM_INFO || '';\n"
)


def update_env(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    for key, value in values.items():
        entry = f"{key}={value}"
        for index, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[index] = entry
                print(f"  = {key} (updated)")
                break
        else:
            lines.append(entry)
            print(f"  + {key}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_config(path: Path) -> None:
    content = path.read_text(encoding="utf-8")

    if "export const METRICS_URL" in content:
        print("  = METRICS_URL export: already present")
    else:
        marker = "export const MODEL_URL: string ="
        if marker in content:
            content = content.replace(marker, METRICS_BLOCK + marker, 1)
        else:
            content = content.rstrip("\n") + "\n\n" + METRICS_BLOCK
        print("  + METRICS_URL export")

    if "export const SYSTEM_INFO" in content:
        print("  = SYSTEM_INFO export: already present")
    else:
        content = content.rstrip("\n") + "\n\n" + SYSTEM_INFO_BLOCK
        print("  + SYSTEM_INFO export")

    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--metrics-url", required=True)
    parser.add_argument("--system-info", required=True)
    parser.add_argument("--max-tokens", default="32768")
    args = parser.parse_args()

    ui_dir = Path(args.work_dir) / "ui" / "react"

    update_env(
        ui_dir / ".env",
        {
            "VITE_MAX_TOKENS": args.max_tokens,
            "VITE_METRICS_SERVICE_ENDPOINT": args.metrics_url,
            "VITE_SYSTEM_INFO": args.system_info,
        },
    )
    update_config(ui_dir / "src" / "config.ts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

