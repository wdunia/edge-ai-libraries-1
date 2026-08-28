#!/usr/bin/env bash
# Stop the Local Chat Bot demo.
#
# Removes demo containers only. Downloaded/converted models (OVMS_MODELS_DIR and
# MODEL_DOWNLOAD_MODEL_PATH) and the working copy are always kept, so the next
# start is fast.

set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEMO_ROOT}/scripts/lib.sh"

QUIET=false
PURGE_MODELS=false

usage() {
    cat <<'EOF'
Usage: ./scripts/stop_local_chat_bot.sh [--quiet] [--purge-models]

  --quiet          Less output (used internally by the launcher).
  --purge-models   Also delete the persistent OVMS model cache.
                   WARNING: the next run downloads and converts models again.
  --help, -h       Show this message.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --quiet) QUIET=true ;;
        --purge-models) PURGE_MODELS=true ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
    shift
done

say() { [[ "${QUIET}" == "true" ]] || echo "$@"; }

require_cmd docker


if [[ -f "${WORK_DIR}/docker-compose.yaml" ]]; then
    say "--> Stopping ChatQnA stack"
    run_docker_cmd "COMPOSE_PROJECT_NAME=$(printf '%q' "${COMPOSE_PROJECT_NAME}") docker compose -f $(printf '%q' "${WORK_DIR}/docker-compose.yaml") -f $(printf '%q' "$(demo_compose_file)") down --remove-orphans >/dev/null 2>&1 || true" || true
fi

say "--> Removing demo containers"
run_docker_cmd "docker rm -f metrics-manager model-download pgvector_db reranker_tei dataprep_pgvector chatqna-ui ovms-service tei-embedding-service minio-server >/dev/null 2>&1 || true" || true
run_docker_cmd "docker ps -aq --filter label=com.docker.compose.project=${COMPOSE_PROJECT_NAME} | xargs -r docker rm -f >/dev/null 2>&1 || true" || true
run_docker_cmd "docker ps -aq --filter label=com.docker.compose.project=chat-question-and-answer | xargs -r docker rm -f >/dev/null 2>&1 || true" || true
run_docker_cmd "docker network rm ${COMPOSE_PROJECT_NAME}_my_network chat-question-and-answer_my_network >/dev/null 2>&1 || true" || true

if [[ "${PURGE_MODELS}" == "true" ]]; then
    say "--> Deleting model cache: ${OVMS_MODELS_DIR}"
    rm -rf "${OVMS_MODELS_DIR}"
fi

say ""
say "Demo stopped. Model cache kept in: ${OVMS_MODELS_DIR}"

