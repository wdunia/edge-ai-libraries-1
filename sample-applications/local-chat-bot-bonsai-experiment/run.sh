#!/usr/bin/env bash
# Opt-in comparison stack. The demo's own launcher and default Compose stay unchanged.
set -euo pipefail

EXPERIMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${EXPERIMENT_DIR}/../local-chat-bot-demo" && pwd)"
variant="${1:-}"
case "${variant}" in
    bonsai-1bit) repo_id="Wondernutts/Bonsai-27B-INTBIT-OpenVINO-Arc" ;;
    bonsai-ternary) repo_id="Wondernutts/Bonsai-27B-INTERNARY-OpenVINO-Arc" ;;
    *) echo "Usage: ./run.sh bonsai-1bit|bonsai-ternary" >&2; exit 2 ;;
esac

[[ -z "${HUGGINGFACEHUB_API_TOKEN:-}${HF_TOKEN:-}" ]] ||
    { echo "Run the experiment without Hugging Face tokens." >&2; exit 1; }
export WORK_ROOT="${EXPERIMENT_DIR}/.work"
export WORK_DIR="${WORK_ROOT}/chat-question-and-answer"
export OVMS_MODELS_DIR="${DEMO_DIR}/.cache/ovms"
export MODEL_DOWNLOAD_REUSE=false
export BONSAI_EXPERIMENT_DIR="${EXPERIMENT_DIR}"
export BONSAI_VARIANT="${variant}"
export BONSAI_MODEL_DIR="${EXPERIMENT_DIR}/models/${variant}"
export BONSAI_COMPILE_DIR="${EXPERIMENT_DIR}/.cache/${variant}"
export BONSAI_REPO_ID="${repo_id}"
mkdir -p "${BONSAI_COMPILE_DIR}"
python3 "${EXPERIMENT_DIR}/verify_bonsai.py" "${BONSAI_MODEL_DIR}" "${variant}"

# Sourcing keeps the demo's exported Compose variables in this process.
# Its working copy is redirected into this experiment and recreated each run.
# shellcheck disable=SC1091
source "${DEMO_DIR}/scripts/run_local_chat_bot.sh" --device GPU --clean --skip-install --no-autorun

compose=(docker compose -f "${WORK_DIR}/docker-compose.yaml"
    -f "${DEMO_DIR}/docker/docker-compose.demo.yaml"
    -f "${EXPERIMENT_DIR}/compose.demo.yaml")
run_docker_cmd "$(printf '%q ' "${compose[@]}") stop ovms-service-gpu chatqna"
python3 "${EXPERIMENT_DIR}/prepare.py" --work-dir "${WORK_DIR}" --ovms-dir "${OVMS_MODELS_DIR}"

echo "Starting ${variant} in the disposable comparison stack (no host plugin replacement)."
run_docker_cmd "$(printf '%q ' "${compose[@]}") up -d --build --force-recreate"
wait_for_chatqna_health "http://localhost:8100/health" "${MAX_WAIT_SECONDS}"
echo "Comparison UI: http://localhost:8101"
echo "Stop: ${EXPERIMENT_DIR}/stop.sh"
