#!/usr/bin/env bash
#
# One-time local build for the two demo images that are NOT published anywhere externally:
#   - dlstreamer-pipeline-server demo backend (FastAPI)
#   - dlstreamer-pipeline-server demo UI (React + nginx)
#
# This script is fully self-contained: it only uses files inside this folder
# (sample-applications/dlstreamer-multiplication-demo). It does NOT read from
# microservices/dlstreamer-pipeline-server.
#
# After running this once, docker-compose.images.yml can start the whole stack
# using image: references only (no build: steps at runtime).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BE_IMAGE_TAG="${DLSTREAMER_DEMO_BE_IMAGE:-dlstreamer-multiplication-demo-be:local}"
UI_IMAGE_TAG="${DLSTREAMER_DEMO_UI_IMAGE:-dlstreamer-multiplication-demo-ui:local}"
BE_BUILD_TARGET="${BE_BUILD_TARGET:-prod}"

echo "=== Building backend image: ${BE_IMAGE_TAG} ==="
docker build \
    --target "${BE_BUILD_TARGET}" \
    -f "${PROJECT_ROOT}/docker/Dockerfile" \
    -t "${BE_IMAGE_TAG}" \
    "${PROJECT_ROOT}"

echo "=== Building UI image: ${UI_IMAGE_TAG} ==="
docker build \
    -f "${PROJECT_ROOT}/src/ui/react/Dockerfile" \
    -t "${UI_IMAGE_TAG}" \
    "${PROJECT_ROOT}/src/ui/react"

echo ""
echo "Done. Update docker/.env with:"
echo "  DLSTREAMER_DEMO_BE_IMAGE=${BE_IMAGE_TAG}"
echo "  DLSTREAMER_DEMO_UI_IMAGE=${UI_IMAGE_TAG}"
echo ""
echo "Then run: ./scripts/run_dlStreamer.sh"

