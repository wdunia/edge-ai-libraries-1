#!/usr/bin/env bash
# Demo-only chat template tuning.
#
# OpenVINO/gpt-oss-20b-int4-ov streams its chain-of-thought before the final
# answer, which is unusable in a live demo.  Forcing the "final" channel in the
# generated OVMS chat template hides the reasoning output.
#
# Runs AFTER setup.sh generated the OVMS model files.  Every chat_template.ninja
# belonging to the model is patched, regardless of the directory layout produced
# by the model-download service.
#
# Idempotent: re-running on an already tuned template is a no-op.

set -euo pipefail

OVMS_DIR="${1:?usage: tune_chat_template.sh <ovms-dir> [model-name]}"
MODEL_NAME="${2:-OpenVINO/gpt-oss-20b-int4-ov}"

ORIGINAL='{- "<|start|>assistant" }}'
TUNED='{- "<|start|>assistant<|channel|>final<|message|>" }}'

if [[ ! -d "${OVMS_DIR}" ]]; then
    echo "WARNING: OVMS directory not found, skipping chat template tuning: ${OVMS_DIR}" >&2
    exit 0
fi

mapfile -t templates < <(find "${OVMS_DIR}" -type f -name 'chat_template.ninja' -path "*${MODEL_NAME}*" 2>/dev/null)

if (( ${#templates[@]} == 0 )); then
    echo "WARNING: no chat_template.ninja found for '${MODEL_NAME}' under ${OVMS_DIR}" >&2
    exit 0
fi

for template in "${templates[@]}"; do
    if grep -qF "${TUNED}" "${template}"; then
        echo "  = already tuned: ${template}"
        continue
    fi

    if ! grep -qF "${ORIGINAL}" "${template}"; then
        echo "WARNING: tuning anchor not found, leaving untouched: ${template}" >&2
        continue
    fi

    python3 - "${template}" "${ORIGINAL}" "${TUNED}" <<'PY'
import sys
from pathlib import Path

path, original, tuned = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
path.write_text(path.read_text(encoding="utf-8").replace(original, tuned), encoding="utf-8")
PY

    echo "  + tuned (reasoning output suppressed): ${template}"
done
