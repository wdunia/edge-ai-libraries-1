#!/usr/bin/env bash

set -euo pipefail

if command -v tput >/dev/null 2>&1; then
    tput clear || true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"
MODEL_DOWNLOAD_DIR="${REPO_ROOT}/microservices/model-download"
UI_DIR="${APP_ROOT}/ui/react"
TOOLS_DIR="${APP_ROOT}/tools"
COMPOSE_FILE="${APP_ROOT}/docker-compose.yaml"
UI_ENV_FILE="${UI_DIR}/.env"

SYSTEM_INFO_TEXT="CPU: Intel Core i7 265H | GPU: Intel Arc B350 | NPU: Intel Ai Boost | RAM: 64GB"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-1800}"
FORCE_RESTART=false
TARGET_DEVICE="${CHATQNA_TARGET_DEVICE:-${DEVICE:-}}"
HF_TOKEN_OVERRIDE="${HUGGINGFACEHUB_API_TOKEN:-}"
MODEL_DOWNLOAD_MODEL_PATH="${MODEL_DOWNLOAD_MODEL_PATH:-${HOME}/host_path}"

TEMP_DIR="$(mktemp -d)"

cleanup() {
    local exit_code=$?

    if [[ -f "${TEMP_DIR}/ui.env.backup" ]]; then
        cp "${TEMP_DIR}/ui.env.backup" "${UI_ENV_FILE}"
    fi

    rm -rf "${TEMP_DIR}"
    exit "${exit_code}"
}

trap cleanup EXIT

usage() {
    cat <<'EOF'
Usage: ./run_chatQnA.sh [--force-restart|-f] [--device CPU|GPU] [--hf-token <token>] [--help]

Options:
  --force-restart, -f    Stop existing related tmux sessions/containers before startup.
  --device               Target device for OVMS model conversion/inference (CPU or GPU).
                         Fallback order: --device -> CHATQNA_TARGET_DEVICE/DEVICE env -> prompt.
  --hf-token             Hugging Face API token. Fallback: HUGGINGFACEHUB_API_TOKEN env -> prompt.
  --help, -h             Show this help message.

Environment overrides:
  MODEL_DOWNLOAD_MODEL_PATH  Host directory mounted into model-download service.
                             Default: $HOME/host_path
  MAX_WAIT_SECONDS           Health-check timeout in seconds. Default: 1800
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force-restart|-f)
                FORCE_RESTART=true
                ;;
            --device)
                shift
                if [[ $# -eq 0 ]]; then
                    echo "Missing value for --device" >&2
                    usage >&2
                    exit 1
                fi
                TARGET_DEVICE="$1"
                ;;
            --hf-token)
                shift
                if [[ $# -eq 0 ]]; then
                    echo "Missing value for --hf-token" >&2
                    usage >&2
                    exit 1
                fi
                HF_TOKEN_OVERRIDE="$1"
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

validate_input() {
    local input="$1"
    case "${input^^}" in
        CPU|GPU)
            return 0
            ;;
        NPU)
            echo "FATAL EXCEPTION! NPU STATUS: NOT_IMPLEMENTED BY SAMPLE APP! SCRIPT WILL HALT!" >&2
            return 1
            ;;
        *)
            return 1
            ;;
    esac
}

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

run_docker_cmd() {
    sg docker -c "$1"
}

container_exists() {
    local name="$1"
    [[ -n "$(run_docker_cmd "docker ps -aq --filter name=^/${name}$")" ]]
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

ensure_tmux_session_running() {
    local session_name="$1"
    local wait_seconds="${2:-2}"

    sleep "$wait_seconds"
    if ! tmux has-session -t "$session_name" 2>/dev/null; then
        echo "ERROR: tmux session '${session_name}' exited unexpectedly." >&2
        echo "Check logs with: tmux attach-session -t ${session_name}" >&2
        return 1
    fi
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

wait_for_model_download_health() {
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

raise SystemExit(0 if data.get("status") == "ok" else 1)
PY
        then
            return 0
        fi

        if (( $(date +%s) - start_ts >= timeout_seconds )); then
            echo "Timed out waiting for model-download health endpoint: $url" >&2
            return 1
        fi

        echo "waiting for model-download health..."
        sleep 1
    done
}

wait_for_chatqna_health() {
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

if not isinstance(data, list):
    raise SystemExit(1)

expected = {"LLM model server", "Embedding model server"}
healthy = {
    item.get("details", "").replace(" is ready to serve", "")
    for item in data
    if isinstance(item, dict) and item.get("status") == "healthy"
}

raise SystemExit(0 if expected.issubset(healthy) else 1)
PY
        then
            return 0
        fi

        if (( $(date +%s) - start_ts >= timeout_seconds )); then
            echo "Timed out waiting for ChatQnA health endpoint: $url" >&2
            return 1
        fi

        echo "waiting for ChatQnA health..."
        sleep 1
    done
}

restart_existing_runtime_if_needed() {
    local has_tmux=false
    local has_containers=false

    if tmux has-session -t metrics-manager 2>/dev/null || \
       tmux has-session -t model_download 2>/dev/null || \
       tmux has-session -t chatqna 2>/dev/null; then
        has_tmux=true
    fi

    for container_name in \
        metrics-manager \
        model-download \
        pgvector_db \
        reranker_tei \
        dataprep_pgvector \
        chatqna-ui \
        ovms-service; do
        if container_exists "$container_name"; then
            has_containers=true
            break
        fi
    done

    if [[ "$FORCE_RESTART" == "false" ]] && { [[ "$has_tmux" == "true" ]] || [[ "$has_containers" == "true" ]]; }; then
        echo "Existing runtime detected (tmux sessions and/or Docker containers)." >&2
        echo "Run again with --force-restart to restart cleanly." >&2
        echo "Example: ./run_chatQnA.sh --force-restart" >&2
        exit 1
    fi

    if [[ "$FORCE_RESTART" == "true" ]]; then
        echo "=== FORCE RESTART ENABLED: STOPPING EXISTING RUNTIME ==="

        tmux kill-session -t chatqna 2>/dev/null || true
        tmux kill-session -t model_download 2>/dev/null || true
        tmux kill-session -t metrics-manager 2>/dev/null || true

        run_docker_cmd "docker rm -f metrics-manager model-download pgvector_db reranker_tei dataprep_pgvector chatqna-ui ovms-service >/dev/null 2>&1 || true" || true
        run_docker_cmd "docker ps -aq --filter label=com.docker.compose.project=chat-question-and-answer | xargs -r docker rm -f >/dev/null 2>&1 || true" || true
        run_docker_cmd "docker network rm chat-question-and-answer_my_network >/dev/null 2>&1 || true" || true
    fi
}

prompt_for_token_if_needed() {
    if [[ -z "$HF_TOKEN_OVERRIDE" ]]; then
        read -r -p "provide a HuggingFace Api Token for model download: " HF_TOKEN_OVERRIDE
    fi

    if [[ -z "$HF_TOKEN_OVERRIDE" ]]; then
        echo "Hugging Face API token cannot be empty." >&2
        exit 1
    fi
}

prompt_for_device_if_needed() {
    while true; do
        if [[ -z "$TARGET_DEVICE" ]]; then
            read -r -p "Please enter a target device (CPU, GPU): " TARGET_DEVICE
        fi

        TARGET_DEVICE="${TARGET_DEVICE^^}"

        if validate_input "$TARGET_DEVICE"; then
            echo "Valid input: $TARGET_DEVICE"
            break
        fi

        echo "Invalid input. Please enter one of: CPU, GPU"
        TARGET_DEVICE=""
    done
}

configure_runtime_env() {
    local ip="$1"

    export HUGGINGFACEHUB_API_TOKEN="${HF_TOKEN_OVERRIDE}"
    export LLM_MODEL="OpenVINO/gpt-oss-20b-int4-ov"
    export EMBEDDING_MODEL_NAME="nomic-ai/nomic-embed-text-v1.5"
    export RERANKER_MODEL="BAAI/bge-reranker-base"
    export DEVICE="${TARGET_DEVICE}"
    export MODEL_DOWNLOAD_HOST="$ip"
    export MODEL_DOWNLOAD_PORT=8200
    export ALLOWED_HOSTS="*"
    export REGISTRY="intel/"
    export TAG=latest
    export APP_METRICS_URL="http://$ip:8100/metrics"
    export HOST_IP="$ip"
    export GETI_SERVER_SSL_VERIFY=False
}

install_dependencies() {
    echo "=== ADD CHROME GPG KEY ==="
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -

    echo "=== UPDATE SYSTEM ==="
    sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list'
    sudo apt update && sudo apt upgrade -y

    echo "=== INSTALL DEPENDENCIES ==="
    sudo apt install -y ca-certificates curl gnupg git jq yq intel-gpu-tools python3-poetry google-chrome-stable python3-venv python3-pip

    echo "=== INSTALL DOCKER ==="
    sudo install -m 0755 -d /etc/apt/keyrings

    if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    fi

    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    sudo usermod -aG docker "$USER"
    sudo chown root:docker /var/run/docker.sock
    sudo chmod 660 /var/run/docker.sock

    echo "=== INSTALL TMUX ==="
    sudo apt install -y tmux
}

main() {
    parse_args "$@"

    require_file "${COMPOSE_FILE}"
    require_file "${UI_ENV_FILE}"

    install_dependencies

    require_cmd curl
    require_cmd docker
    require_cmd jq
    require_cmd python3
    require_cmd sg
    require_cmd tmux

    echo "=== SETTING ENVIRONMENT VARIABLES ==="
    prompt_for_token_if_needed
    prompt_for_device_if_needed

    local ip
    ip="$(hostname -I | awk '{print $1}')"
    [[ -n "$ip" ]] || {
        echo "Could not determine host IP address." >&2
        exit 1
    }

    configure_runtime_env "$ip"
    mkdir -p "${MODEL_DOWNLOAD_MODEL_PATH}"

    restart_existing_runtime_if_needed

    cp "${UI_ENV_FILE}" "${TEMP_DIR}/ui.env.backup"

    echo "Using target device: ${DEVICE}"
    echo "Using host IP: ${ip}"
    echo "Using model-download host path: ${MODEL_DOWNLOAD_MODEL_PATH}"

    local model_download_model_path_quoted
    printf -v model_download_model_path_quoted '%q' "${MODEL_DOWNLOAD_MODEL_PATH}"

    echo " === STARTING METRICS_SERVER CONTAINER ==="

    start_tmux_session \
        "metrics-manager" \
        "${APP_ROOT}" \
        "sg docker -c 'docker run --rm --privileged --name metrics-manager --device /dev/dri -p 9090:9090 -p 9273:9273 -v /sys:/sys:ro -v /run:/run:ro --pid host intel/metrics-manager:2026.1.0-20260508-weekly'"

echo "=== STARTING MODEL DOWNLOAD MICROSERVICE (REQUIRED TO DOWNLOAD TARGET_MODEL) ==="
echo "--> To attach to model download TMUX session type: tmux attach-session -t model_download"
    start_tmux_session \
        "model_download" \
        "${MODEL_DOWNLOAD_DIR}" \
        "sg docker -c 'bash -c \"source scripts/run_service.sh up --plugins all --model-path ${model_download_model_path_quoted}\"'"

    ensure_tmux_session_running "metrics-manager" 2
    ensure_tmux_session_running "model_download" 2

echo "=== CONTAINERS STARTED IN THE BACKGROUND, WAITING FOR API HEALTHY MESSAGE ==="
    wait_for_model_download_health "http://localhost:8200/health" "${MAX_WAIT_SECONDS}"

    cd "${APP_ROOT}"

echo "=== MODEL TUNING ==="
# As model OpenVINO/gpt-oss-20b-int4-ov has an "ugly" behavior that it display it's reasoning process and don't want this on screen
# we supress this behavior by some tricky workaround.
# Of course we could train model from scratch but this could take ashes and we don't have such time.
echo "Model template tuning will run after setup.sh prepares OVMS files."

echo "=== UPDATING REQUIRED ENVIRONMENT VARIABLES ==="
# Due to issue where during container build process env variables are converted into static values before env variables are set
# there was a need for injecting static values into env file(s).
# Attention! This is TEMPORARY WORKAROUND. A proper fix in docker-compose logic is needed.
# For DEMO purpose only!
# Do NOT poropose this as final solution.

    update_env_var "${UI_ENV_FILE}" "VITE_MAX_TOKENS" "32768"
    update_env_var "${UI_ENV_FILE}" "VITE_METRICS_SERVICE_ENDPOINT" "http://${ip}:8100/metrics"
    update_env_var "${UI_ENV_FILE}" "VITE_SYSTEM_INFO" "${SYSTEM_INFO_TEXT}"

echo "=== STARTING CHAT QNA SAMPLE APP IN THE BACKGROUND ==="
    start_tmux_session \
        "chatqna" \
        "${APP_ROOT}" \
        "bash -c 'source setup.sh llm=OVMS embed=OVMS; if [[ -f ovms/OpenVINO/gpt-oss-20b-int4-ov/chat_template.ninja ]]; then sed -i '\''s/{- \"<|start|>assistant\" }}/{- \"<|start|>assistant<|channel|>final<|message|>\" }}/g'\'' ovms/OpenVINO/gpt-oss-20b-int4-ov/chat_template.ninja; else echo \"WARNING: chat template not found, skipping tuning\" >&2; fi; sg docker -c \"docker compose up --build\"'"

    ensure_tmux_session_running "chatqna" 2

echo "=== CONTAINERS STARTED IN THE BACKGROUND, WAITING FOR API HEALTHY MESSAGE ==="
echo "---> To open TMUX session with chatqna open new terminal session and type: tmux attach-session -t chatqna"

    wait_for_chatqna_health "http://localhost:8100/health" "${MAX_WAIT_SECONDS}"

echo "=== WE ARE ALL SET! STARTING PROMPT SUBMISSION CLI TOOL ==="

    cd "${TOOLS_DIR}"
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -r requirements.txt
    python3 autorun.py

    read -n 1 -s -r -p "Press any key to continue after you have finished using the application..."
}

main "$@"
