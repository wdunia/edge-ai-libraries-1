#!/usr/bin/env python3
"""Demo-only npm dependencies for the working copy.

The demo UI adds live metric charts and markdown rendering; those packages are
not part of the sample application.  Dependencies are declared here instead of
patching ``package.json`` so that upstream dependency bumps never conflict.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEMO_DEPENDENCIES = {
    "chart.js": "^4.5.1",
    "react-chartjs-2": "^5.3.0",
    "react-markdown": "^10.1.0",
    "remark-gfm": "^4.0.1",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    path = Path(args.work_dir) / "ui" / "react" / "package.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    deps = data.setdefault("dependencies", {})

    changed = False
    for name, version in sorted(DEMO_DEPENDENCIES.items()):
        if deps.get(name) == version:
            print(f"  = {name}@{version}")
            continue
        deps[name] = version
        changed = True
        print(f"  + {name}@{version}")

    if changed:
        data["dependencies"] = dict(sorted(deps.items()))
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

