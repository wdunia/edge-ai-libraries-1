#!/usr/bin/env python3
"""Demo-only tweaks for the sample application ``setup.sh``.

Applied to the working copy only - the sample application in the repository is
never touched.  All replacements are idempotent, so re-running the generator is
safe.  Rationale for every change is documented inline.
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="path to the working copy setup.sh")
    parser.add_argument("--max-tokens", default="32768")
    parser.add_argument("--job-max-attempts", default="240")
    parser.add_argument("--status-log-every", default="10")
    args = parser.parse_args()

    path = Path(args.file)
    content = path.read_text(encoding="utf-8")

    # Keep converted OVMS models outside the throwaway working copy, otherwise
    # recreating it would trigger another multi-hour download/convert cycle.
    content = replace_once(
        content,
        "export VOLUME_OVMS=${PWD}/ovms\n",
        "export VOLUME_OVMS=${VOLUME_OVMS:-${PWD}/ovms}\n",
        "respect externally provided VOLUME_OVMS",
    )

    # The demo runs a long-context model, the upstream default is far too small.
    content = replace_once(
        content,
        "export MAX_TOKENS=1024\n",
        f"export MAX_TOKENS={args.max_tokens}\n",
        "MAX_TOKENS for the demo model",
    )

    # Model conversion of a 20B model easily exceeds the upstream 5 minute budget.
    content = replace_once(
        content,
        "    local MAX_ATTEMPTS=60\n",
        f'    local MAX_ATTEMPTS="${{MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS:-{args.job_max_attempts}}}"\n',
        "longer model-download polling window",
    )

    # Re-running the demo must not re-download/re-convert an already converted model.
    content = replace_once(
        content,
        '    echo -e "${BLUE}Downloading $MODEL_TYPE model \'$MODEL_NAME\' via model-download...\\n${NC}"\n',
        '    local EXISTING_MODEL_DIR="${TARGET_DIR}${MODEL_NAME}"\n\n'
        "    # Reuse previously converted OVMS model if already present.\n"
        '    if [[ -d "$EXISTING_MODEL_DIR" ]] && find "$EXISTING_MODEL_DIR" -mindepth 1 -print -quit >/dev/null 2>&1; then\n'
        "        echo -e \"${GREEN}Model '$MODEL_NAME' already present in '$EXISTING_MODEL_DIR'. Skipping download.${NC}\\n\"\n"
        "        return 0\n"
        "    fi\n\n"
        '    echo -e "${BLUE}Downloading $MODEL_TYPE model \'$MODEL_NAME\' via model-download...\\n${NC}"\n',
        "skip download of already converted models",
    )

    # Polling every 5s for up to 20 minutes floods the log with identical lines.
    content = replace_once(
        content,
        "    declare -A job_done\n    declare -A job_conversion_path\n",
        "    declare -A job_done\n"
        "    declare -A job_conversion_path\n"
        "    declare -A job_last_status\n\n"
        f'    local status_log_every="${{MODEL_DOWNLOAD_STATUS_LOG_EVERY:-{args.status_log_every}}}"\n',
        "state for throttled status logging",
    )

    content = replace_once(
        content,
        '            echo "Job $job_id → $status"\n',
        '            if [[ "${job_last_status[$job_id]-}" != "$status" || $((attempt % status_log_every)) -eq 0 ]]; then\n'
        '                echo "Job $job_id → $status (attempt $attempt/$MAX_ATTEMPTS)"\n'
        '                job_last_status[$job_id]="$status"\n'
        "            fi\n",
        "throttled job status logging",
    )

    # Upstream swallows download failures; the demo must abort early instead of
    # starting a stack that can never become healthy.
    content = replace_once(
        content,
        '                        download_ovms_model "$LLM_MODEL" "llm" "openvino"\n',
        '                        download_ovms_model "$LLM_MODEL" "llm" "openvino" || return 1\n',
        "propagate LLM download failure",
    )

    content = replace_once(
        content,
        '                        download_ovms_model "$EMBEDDING_MODEL_NAME" "embeddings" "openvino"\n',
        '                        download_ovms_model "$EMBEDDING_MODEL_NAME" "embeddings" "openvino" || return 1\n',
        "propagate embedding download failure",
    )

    content = replace_once(
        content,
        '        setup_inference "$LLM_SERVICE"\n        setup_embedding "$EMBED_SERVICE"\n',
        '        setup_inference "$LLM_SERVICE" || return 1\n        setup_embedding "$EMBED_SERVICE" || return 1\n',
        "propagate setup failures to the caller",
    )

    path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

