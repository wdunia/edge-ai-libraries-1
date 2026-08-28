#!/usr/bin/env bash
# Shared helpers for the Local Chat Bot demo scripts.
# Expects DEMO_ROOT to be set by the caller before sourcing.

set -euo pipefail

if [[ -z "${DEMO_ROOT:-}" ]]; then
    echo "DEMO_ROOT must be set before sourcing lib.sh" >&2
    exit 1
fi

# shellcheck disable=SC1091
source "${DEMO_ROOT}/scripts/demo.env"

REPO_ROOT="$(cd "${DEMO_ROOT}/../.." && pwd)"
APP_SOURCE_DIR="${REPO_ROOT}/${APP_REL_PATH}"

log()  { echo -e "\n=== $* ==="; }
info() { echo "--> $*"; }
warn() { echo "WARNING: $*" >&2; }
die()  { echo "ERROR: $*" >&2; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

require_workspace() {
    [[ -d "${WORK_DIR}" ]] || die "Working copy not found: ${WORK_DIR}. Run scripts/prepare_workspace.sh first."
}

# Docker is used either directly or through `sg docker` when the current shell
# session does not have the docker group applied yet (fresh install).
docker_is_usable() {
    docker info >/dev/null 2>&1
}

run_docker_cmd() {
    local cmd="$1"
    if docker_is_usable; then
        bash -c "${cmd}"
    elif command_exists sg; then
        sg docker -c "${cmd}"
    else
        die "Docker is not accessible for the current user (and 'sg' is unavailable)."
    fi
}


# Path to the demo compose override that is merged on top of the pristine
# docker-compose.yaml shipped with the sample application.
demo_compose_file() {
    echo "${DEMO_ROOT}/docker/docker-compose.demo.yaml"
}


