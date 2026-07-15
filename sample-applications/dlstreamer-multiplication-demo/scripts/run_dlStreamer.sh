#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOCKER_DIR="${PROJECT_ROOT}/docker"
UI_DIR="${PROJECT_ROOT}/src/ui/react"
TOOLS_DIR="${PROJECT_ROOT}/tools"

DOCKER_ENV_FILE="${DOCKER_DIR}/.env"
DOCKER_ENV_EXAMPLE_FILE="${DOCKER_DIR}/.env.example"
UI_ENV_FILE="${UI_DIR}/.env"
COMPOSE_FILE="${DOCKER_DIR}/docker-compose.images.yml"

MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-600}"
FORCE_RESTART=true
FORCE_DOWN=false
AUTO_OPEN_BROWSER=true
SOURCE_MODE="${DLSPS_SOURCE_MODE:-file}"
DEFAULT_STREAM_URL="${DEFAULT_RTSP_SOURCE_URL:-rtsp://host.docker.internal:8554/camera0}"
MODEL_PATH_IN_CONTAINER="${MODEL_PATH_IN_CONTAINER:-/home/pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml}"
SYSTEM_INFO_TEXT="${SYSTEM_INFO_TEXT:-CPU/GPU/NPU telemetry via prebuilt images}"

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing required command: $1" >&2
        exit 1
    }
}

require_file() {
    [[ -f "$1" ]] || {
        echo "Required file not found: $1" >&2
        exit 1
    }
}

usage() {
    cat <<EOF
Usage: ./run_dlStreamer.sh [--force-restart|-f] [--open-browser|--no-open-browser] [--source-mode file|rtsp] [--help]

Starts the demo stack from prebuilt images. On first run it also generates
docker/.env and builds the two custom demo images if they are missing.

Options:
  --force-restart, -f   Restart existing demo containers first (default behavior).
  --no-force-restart    Skip restarting existing demo containers before startup.
  --compose-down        Run docker compose down --remove-orphans before startup.
  --open-browser        Force opening the browser after services are up.
  --no-open-browser     Skip opening the browser automatically.
  --source-mode         Default source shown in the UI: file (default) or rtsp.
  --help, -h            Show this help message.
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force-restart|-f)
                FORCE_RESTART=true
                ;;
            --no-force-restart)
                FORCE_RESTART=false
                ;;
            --compose-down)
                FORCE_DOWN=true
                ;;
            --open-browser)
                AUTO_OPEN_BROWSER=true
                ;;
            --no-open-browser)
                AUTO_OPEN_BROWSER=false
                ;;
            --source-mode)
                shift
                if [[ $# -eq 0 ]]; then
                    echo "Missing value for --source-mode" >&2
                    usage >&2
                    exit 1
                fi
                SOURCE_MODE="$1"
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                echo "Unknown argument: $1" >&2
                usage >&2
                exit 1
                ;;
        esac
        shift
    done

    case "$SOURCE_MODE" in
        file|rtsp)
            ;;
        *)
            echo "Invalid --source-mode value: $SOURCE_MODE" >&2
            usage >&2
            exit 1
            ;;
    esac
}

update_env_var() {
    local file_path="$1"
    local key="$2"
    local value="$3"

    python3 - "$file_path" "$key" "$value" <<'PY'
from pathlib import Path
import sys

file_path, key, value = sys.argv[1:]
path = Path(file_path)
lines = path.read_text(encoding="utf-8").splitlines()

updated = False
for index, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[index] = f"{key}={value}"
        updated = True
        break

if not updated:
    lines.append(f"{key}={value}")

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

wait_for_http_200() {
    local url="$1"
    local timeout_seconds="$2"
    local label="$3"
    local start_ts

    start_ts="$(date +%s)"
    while true; do
        if curl -fsS "$url" >/dev/null 2>&1; then
            return 0
        fi
        if (( $(date +%s) - start_ts >= timeout_seconds )); then
            echo "Timed out waiting for ${label}: $url" >&2
            return 1
        fi
        sleep 1
    done
}

start_services() {
    local compose_cmd=(docker compose --env-file "${DOCKER_ENV_FILE}" -f "${COMPOSE_FILE}")

    if [[ "$FORCE_DOWN" == "true" ]]; then
        "${compose_cmd[@]}" down --remove-orphans || true
    elif [[ "$FORCE_RESTART" == "true" ]]; then
        "${compose_cmd[@]}" stop || true
    fi

    "${compose_cmd[@]}" up -d
}

check_demo_images_present() {
    local be_image ui_image
    be_image="$(grep -E '^DLSTREAMER_DEMO_BE_IMAGE=' "${DOCKER_ENV_FILE}" | cut -d= -f2-)"
    ui_image="$(grep -E '^DLSTREAMER_DEMO_UI_IMAGE=' "${DOCKER_ENV_FILE}" | cut -d= -f2-)"

    if docker image inspect "${be_image}" >/dev/null 2>&1 && \
       docker image inspect "${ui_image}" >/dev/null 2>&1; then
        return 0
    fi

    echo "=== BUILDING MISSING DEMO IMAGES (one-time, self-contained) ==="
    "${SCRIPT_DIR}/build_demo_images.sh"
}

ensure_docker_env_file() {
    if [[ -f "${DOCKER_ENV_FILE}" ]]; then
        return 0
    fi

    require_file "${DOCKER_ENV_EXAMPLE_FILE}"

    echo "=== GENERATING docker/.env FROM TEMPLATE (first run) ==="
    cp "${DOCKER_ENV_EXAMPLE_FILE}" "${DOCKER_ENV_FILE}"

    local random_password random_username
    if command -v openssl >/dev/null 2>&1; then
        random_password="$(openssl rand -hex 16)"
    else
        random_password="$(date +%s%N)$$"
    fi
    random_username="demo-$(date +%s)"

    update_env_var "${DOCKER_ENV_FILE}" "MTX_WEBRTCICESERVERS2_0_USERNAME" "${random_username}"
    update_env_var "${DOCKER_ENV_FILE}" "MTX_WEBRTCICESERVERS2_0_PASSWORD" "${random_password}"

    echo "Generated docker/.env with a random TURN password (not committed to git)."
}

main() {
    parse_args "$@"

    require_cmd docker
    require_cmd curl
    require_cmd python3
    require_file "${UI_ENV_FILE}"
    require_file "${COMPOSE_FILE}"

    ensure_docker_env_file
    check_demo_images_present

    local ip
    local default_stream_url

    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [[ -z "$ip" ]]; then
        ip="127.0.0.1"
    fi

    if [[ "$SOURCE_MODE" == "file" ]]; then
        default_stream_url="file:///home/pipeline-server/resources/videos/warehouse.avi"
    else
        default_stream_url="${DEFAULT_STREAM_URL}"
    fi

    update_env_var "${DOCKER_ENV_FILE}" "ip" "${ip}"
    update_env_var "${DOCKER_ENV_FILE}" "WHIP_SERVER_IP" "${ip}"
    update_env_var "${DOCKER_ENV_FILE}" "VITE_PIPELINE_SERVER_URL" "http://${ip}:8080"
    update_env_var "${DOCKER_ENV_FILE}" "VITE_API_URL" "http://${ip}:8888"
    update_env_var "${DOCKER_ENV_FILE}" "VITE_WEBRTC_URL" "http://${ip}:8889"
    update_env_var "${DOCKER_ENV_FILE}" "VITE_SYSTEM_INFO" "${SYSTEM_INFO_TEXT}"
    update_env_var "${DOCKER_ENV_FILE}" "VITE_MODEL_PATH" "${MODEL_PATH_IN_CONTAINER}"
    update_env_var "${DOCKER_ENV_FILE}" "VITE_DEFAULT_STREAM_URL" "${default_stream_url}"

    update_env_var "${UI_ENV_FILE}" "VITE_PIPELINE_SERVER_URL" "http://${ip}:8080"
    update_env_var "${UI_ENV_FILE}" "VITE_API_URL" "http://${ip}:8888"
    update_env_var "${UI_ENV_FILE}" "VITE_WEBRTC_URL" "http://${ip}:8889"
    update_env_var "${UI_ENV_FILE}" "VITE_SYSTEM_INFO" "${SYSTEM_INFO_TEXT}"
    update_env_var "${UI_ENV_FILE}" "VITE_MODEL_PATH" "${MODEL_PATH_IN_CONTAINER}"
    update_env_var "${UI_ENV_FILE}" "VITE_DEFAULT_STREAM_URL" "${default_stream_url}"

    echo "Starting standalone image-based demo stack..."
    start_services

    echo "Waiting for backend and pipeline server..."
    wait_for_http_200 "http://localhost:8888/health" "${MAX_WAIT_SECONDS}" "demo backend"
    wait_for_http_200 "http://localhost:8080/pipelines/status" "${MAX_WAIT_SECONDS}" "pipeline server"

    echo "Demo is up: http://localhost:8101"

    if [[ "$AUTO_OPEN_BROWSER" == "true" ]]; then
        cd "${TOOLS_DIR}"
        python3 -m venv .venv
        # shellcheck disable=SC1091
        source .venv/bin/activate
        pip install -r requirements.txt
        python3 autorun.py
    fi
}

main "$@"
