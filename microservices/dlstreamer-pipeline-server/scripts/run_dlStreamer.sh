#!/usr/bin/env bash

set -euo pipefail

if command -v tput >/dev/null 2>&1; then
    tput clear || true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOCKER_DIR="${PROJECT_ROOT}/docker"
UI_DIR="${PROJECT_ROOT}/src/ui/react"
TOOLS_DIR="${PROJECT_ROOT}/tools"

DOCKER_ENV_FILE="${DOCKER_DIR}/.env"
UI_ENV_FILE="${UI_DIR}/.env"
COMPOSE_FILE="${DOCKER_DIR}/docker-compose-mediamtx.yml"

DEFAULT_MODEL_PATH="${PROJECT_ROOT}/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml"
SYSTEM_INFO_TEXT="CPU: Intel Core i7 265H | GPU: Intel Arc B350 | NPU: Intel Ai Boost | RAM: 64GB"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-1800}"
FORCE_RESTART=false
MODEL_PATH_OVERRIDE=""

TEMP_DIR="$(mktemp -d)"

cleanup() {
    local exit_code=$?

    if [[ -f "${TEMP_DIR}/docker.env.backup" ]]; then
        cp "${TEMP_DIR}/docker.env.backup" "${DOCKER_ENV_FILE}"
    fi

    if [[ -f "${TEMP_DIR}/ui.env.backup" ]]; then
        cp "${TEMP_DIR}/ui.env.backup" "${UI_ENV_FILE}"
    fi

    rm -rf "${TEMP_DIR}"
    exit "${exit_code}"
}

trap cleanup EXIT

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
    cat <<'EOF'
Usage: ./run_dlStreamer.sh [--force-restart|-f] [--model-path|-m <path>] [--help]

Options:
  --force-restart, -f    Stop existing related tmux sessions/containers before startup.
  --model-path, -m       Path to model.xml used for VITE_MODEL_PATH.
                         Fallback order: --model-path -> MODEL_PATH env -> default path.
  --help, -h             Show this help message.
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force-restart|-f)
                FORCE_RESTART=true
                ;;
            --model-path|-m)
                shift
                if [[ $# -eq 0 ]]; then
                    echo "Missing value for --model-path/-m" >&2
                    usage >&2
                    exit 1
                fi
                MODEL_PATH_OVERRIDE="$1"
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
}

resolve_model_path() {
    local resolved_path=""

    if [[ -n "$MODEL_PATH_OVERRIDE" ]]; then
        resolved_path="$MODEL_PATH_OVERRIDE"
    elif [[ -n "${MODEL_PATH:-}" ]]; then
        resolved_path="${MODEL_PATH}"
    else
        resolved_path="${DEFAULT_MODEL_PATH}"
    fi

    if [[ ! -f "$resolved_path" ]]; then
        echo "model.xml not found: $resolved_path" >&2
        echo "Provide model path using --model-path <path> or MODEL_PATH env." >&2
        echo "Default checked path: ${DEFAULT_MODEL_PATH}" >&2
        exit 1
    fi

    echo "$resolved_path"
}

run_docker_cmd() {
    sg docker -c "$1"
}

compose_ps_any() {
    run_docker_cmd "docker compose --env-file \"${DOCKER_ENV_FILE}\" -f \"${COMPOSE_FILE}\" ps -aq"
}

container_exists() {
    local name="$1"
    [[ -n "$(run_docker_cmd "docker ps -aq --filter name=^/${name}$")" ]]
}

restart_existing_runtime_if_needed() {
    local has_tmux=false
    local has_metrics=false
    local has_compose=false

    if tmux has-session -t metrics-manager 2>/dev/null || \
       tmux has-session -t dlstreamer 2>/dev/null || \
       tmux has-session -t ffmpeg-rtsp 2>/dev/null; then
        has_tmux=true
    fi

    if container_exists "metrics-manager"; then
        has_metrics=true
    fi

    if [[ -n "$(compose_ps_any)" ]]; then
        has_compose=true
    fi

    if [[ "$FORCE_RESTART" == "false" ]] && { [[ "$has_tmux" == "true" ]] || [[ "$has_metrics" == "true" ]] || [[ "$has_compose" == "true" ]]; }; then
        echo "Existing runtime detected (tmux sessions and/or Docker containers)." >&2
        echo "Run again with --force-restart to restart cleanly." >&2
        echo "Example: ./run_dlStreamer.sh --force-restart" >&2
        exit 1
    fi

    if [[ "$FORCE_RESTART" == "true" ]]; then
        echo "=== FORCE RESTART ENABLED: STOPPING EXISTING RUNTIME ==="

        tmux kill-session -t ffmpeg-rtsp 2>/dev/null || true
        tmux kill-session -t dlstreamer 2>/dev/null || true
        tmux kill-session -t metrics-manager 2>/dev/null || true

        run_docker_cmd "docker compose --env-file \"${DOCKER_ENV_FILE}\" -f \"${COMPOSE_FILE}\" down --remove-orphans" || true
        run_docker_cmd "docker rm -f metrics-manager >/dev/null 2>&1 || true" || true
    fi
}

start_tmux_session() {
    local session_name="$1"
    local working_dir="$2"
    local command="$3"

    if tmux has-session -t "$session_name" 2>/dev/null; then
        echo "tmux session '$session_name' already exists. Close it first or attach to it:" >&2
        echo "tmux attach-session -t $session_name" >&2
        exit 1
    fi

    tmux new-session -d -s "$session_name" -c "$working_dir" "$command"
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

wait_for_backend_health() {
    local url="$1"
    local timeout_seconds="$2"
    local start_ts
    local response

    start_ts="$(date +%s)"

    while true; do
        response="$(curl -fsS "$url" 2>/dev/null || true)"

        if [[ -n "$response" ]] && python3 - "$response" <<'PY'
import json
import sys

try:
    data = json.loads(sys.argv[1])
except Exception:
    raise SystemExit(1)

raise SystemExit(
    0
    if data.get("status") == "Success"
    and data.get("message") == "Service is up and running."
    else 1
)
PY
        then
            return 0
        fi

        if (( $(date +%s) - start_ts >= timeout_seconds )); then
            echo "Timed out waiting for backend health endpoint: $url" >&2
            return 1
        fi

        echo "waiting for backend health..."
        sleep 1
    done
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

        echo "waiting for ${label}..."
        sleep 1
    done
}

main() {
    parse_args "$@"

    require_cmd curl
    require_cmd docker
    require_cmd python3
    require_cmd sg
    require_cmd tmux

    require_file "${DOCKER_ENV_FILE}"
    require_file "${UI_ENV_FILE}"
    require_file "${COMPOSE_FILE}"

    restart_existing_runtime_if_needed

    echo "=== CONFIGURE DEMO APP ==="

    local ip
    ip="$(hostname -I | awk '{print $1}')"
    [[ -n "$ip" ]] || {
        echo "Could not determine host IP address." >&2
        exit 1
    }
    export ip="$ip"

    local model_path
    model_path="$(resolve_model_path)"
    export model_path="$model_path"

    echo "Using model_path: $model_path"

    cp "${DOCKER_ENV_FILE}" "${TEMP_DIR}/docker.env.backup"
    cp "${UI_ENV_FILE}" "${TEMP_DIR}/ui.env.backup"

    echo "=== UPDATING REQUIRED ENVIRONMENT VARIABLES ==="
    # Due to issue where during container build process env variables are converted into static values before env variables are set
    # there was a need for injecting static values into env file(s).
    # Attention! This is TEMPORARY WORKAROUND. A proper fix in docker-compose logic is needed.
    # For DEMO purpose only!
    # Do NOT propose this as final solution.
    update_env_var "${DOCKER_ENV_FILE}" "ip" "${ip}"
    update_env_var "${DOCKER_ENV_FILE}" "WHIP_SERVER_IP" "${ip}"
    update_env_var "${UI_ENV_FILE}" "VITE_PIPELINE_SERVER_URL" "http://${ip}:8080"
    update_env_var "${UI_ENV_FILE}" "VITE_API_URL" "http://${ip}:8888"
    update_env_var "${UI_ENV_FILE}" "VITE_WEBRTC_URL" "http://${ip}:8889"
    update_env_var "${UI_ENV_FILE}" "VITE_PROMETHEUS_URL" "http://${ip}:9999"
    update_env_var "${UI_ENV_FILE}" "VITE_SYSTEM_INFO" "${SYSTEM_INFO_TEXT}"
    update_env_var "${UI_ENV_FILE}" "VITE_MODEL_PATH" "${model_path}"
    update_env_var "${UI_ENV_FILE}" "VITE_DEFAULT_STREAM_URL" "rtsp://${ip}:8554/camera0"

    echo " === STARTING METRICS_SERVER CONTAINER ==="
    start_tmux_session \
        "metrics-manager" \
        "${PROJECT_ROOT}" \
        "sg docker -c 'docker run --rm --privileged --name metrics-manager --device /dev/dri -p 9090:9090 -p 9273:9273 -v /sys:/sys:ro -v /run:/run:ro --pid host intel/metrics-manager:2026.1.0-20260508-weekly'"

    echo "=== STARTING DL-STREAMER PIPELINE SERVER MICROSERVICE ==="
    start_tmux_session \
        "dlstreamer" \
        "${PROJECT_ROOT}" \
        "sg docker -c 'docker compose --env-file \"${DOCKER_ENV_FILE}\" -f \"${COMPOSE_FILE}\" up --build'"

    echo "=== CONTAINERS STARTED IN THE BACKGROUND ==="
    echo "---> To open TMUX session with dlstreamer open new terminal session and type: tmux attach-session -t dlstreamer"

    echo "=== WAITING FOR UI BACKEND HEALTH ON :8888 ==="
    wait_for_backend_health "http://localhost:8888/health" "${MAX_WAIT_SECONDS}"

    echo "=== WAITING FOR MAIN PIPELINE SERVER ON :8080 ==="
    wait_for_http_200 "http://localhost:8080/pipelines/status" "${MAX_WAIT_SECONDS}" "pipeline server"

    echo "=== CREATING RTSP STREAM FROM CAMERA ==="
    echo "--> To attach to ffmpeg session type: tmux attach-session -t ffmpeg-rtsp"

    # in case of multiple cameras in system change path to camera f.ex /dev/videoX
    # Attention! ffmpeg command MUST be executed with ROOT access.
    #
    # Do NOT try to use VAAPI (HW) for encoding. RTSP Stream may be broken then. Also it uses GPU processing capacity
    # that should be reserved for DL-Streamer purposes only.
    start_tmux_session \
        "ffmpeg-rtsp" \
        "${PROJECT_ROOT}" \
        "sudo ffmpeg -f v4l2 -i /dev/video0 -c:v libx264 -preset ultrafast -tune zerolatency -f rtsp -rtsp_transport tcp -reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_delay_max 5 rtsp://${ip}:8554/camera0"

    echo "=== WE ARE ALL SET! OPENING BROWSER ==="

    cd "${TOOLS_DIR}"
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -r requirements.txt
    python3 autorun.py
}

main "$@"
