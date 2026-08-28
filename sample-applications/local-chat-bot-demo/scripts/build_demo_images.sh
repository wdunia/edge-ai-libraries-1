#!/usr/bin/env bash
# Build the two demo images from the working copy.
#
# Images are built locally only (never pushed) and tagged separately from the
# official chatqna images so nothing is shadowed on the host.
#
# Normally not needed: run_local_chat_bot.sh builds through `docker compose up
# --build`.  Use this script to pre-build or rebuild manually.

set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEMO_ROOT}/scripts/lib.sh"

require_cmd docker
require_workspace

log "BUILDING BACKEND IMAGE: ${DEMO_BE_IMAGE}"
run_docker_cmd "docker build -f $(printf '%q' "${WORK_DIR}/Dockerfile") -t $(printf '%q' "${DEMO_BE_IMAGE}") $(printf '%q' "${WORK_DIR}")"

log "BUILDING UI IMAGE: ${DEMO_UI_IMAGE}"
run_docker_cmd "docker build -f $(printf '%q' "${WORK_DIR}/ui/react/Dockerfile") -t $(printf '%q' "${DEMO_UI_IMAGE}") $(printf '%q' "${WORK_DIR}/ui/react")"

log "DONE"
info "Backend: ${DEMO_BE_IMAGE}"
info "UI:      ${DEMO_UI_IMAGE}"

