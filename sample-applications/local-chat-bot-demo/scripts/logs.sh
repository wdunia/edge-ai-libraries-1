#!/usr/bin/env bash
# Tail the logs of the Local Chat Bot demo stack.
#
#   ./scripts/logs.sh                # follow the whole ChatQnA stack
#   ./scripts/logs.sh chatqna        # a single compose service
#   ./scripts/logs.sh model-download # supporting containers work too

set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEMO_ROOT}/scripts/lib.sh"

require_cmd docker

TARGET="${1:-}"

case "${TARGET}" in
    model-download|metrics-manager)
        run_docker_cmd "docker logs -f --tail 200 ${TARGET}"
        ;;
    "")
        require_workspace
        run_docker_cmd "COMPOSE_PROJECT_NAME=$(printf '%q' "${COMPOSE_PROJECT_NAME}") docker compose -f $(printf '%q' "${WORK_DIR}/docker-compose.yaml") -f $(printf '%q' "$(demo_compose_file)") logs -f --tail 200"
        ;;
    *)
        require_workspace
        run_docker_cmd "COMPOSE_PROJECT_NAME=$(printf '%q' "${COMPOSE_PROJECT_NAME}") docker compose -f $(printf '%q' "${WORK_DIR}/docker-compose.yaml") -f $(printf '%q' "$(demo_compose_file)") logs -f --tail 200 $(printf '%q' "${TARGET}")"
        ;;
esac

