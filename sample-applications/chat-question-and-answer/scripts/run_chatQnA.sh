#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"
MODEL_DOWNLOAD_DIR="${REPO_ROOT}/microservices/model-download"
UI_DIR="${APP_ROOT}/ui/react"
TOOLS_DIR="${APP_ROOT}/tools"
COMPOSE_FILE="${APP_ROOT}/docker-compose.yaml"
UI_ENV_FILE="${UI_DIR}/.env"
UI_PACKAGE_JSON_FILE="${UI_DIR}/package.json"
UI_CONFIG_FILE="${UI_DIR}/src/config.ts"
UI_METRICS_PANEL_FILE="${UI_DIR}/src/components/Metrics/MetricsPanel.tsx"
UI_DOCKERFILE_FILE="${UI_DIR}/Dockerfile"
APP_DOCKERFILE_FILE="${APP_ROOT}/Dockerfile"
SETUP_SCRIPT_FILE="${APP_ROOT}/setup.sh"
LOG_DIR="${CHATQNA_LOG_DIR:-${APP_ROOT}/logs}"

SYSTEM_INFO_TEXT="CPU: Intel Core i7 265H | GPU: Intel Arc B350 | NPU: Intel Ai Boost | RAM: 64GB"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-1800}"
FORCE_RESTART=false
TARGET_DEVICE="${CHATQNA_TARGET_DEVICE:-${DEVICE:-}}"
HF_TOKEN_OVERRIDE="${HUGGINGFACEHUB_API_TOKEN:-}"
MODEL_DOWNLOAD_MODEL_PATH="${MODEL_DOWNLOAD_MODEL_PATH:-${HOME}/host_path}"
MODEL_DOWNLOAD_IMAGE="${MODEL_DOWNLOAD_IMAGE:-intel/model-download:latest}"
MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS="${MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS:-240}"
MODEL_DOWNLOAD_STATUS_LOG_EVERY="${MODEL_DOWNLOAD_STATUS_LOG_EVERY:-10}"

TEMP_DIR="$(mktemp -d)"
RUNTIME_ENV_FILE="${TEMP_DIR}/chatqna.runtime.env"
SESSION_STATUS_DIR="${TEMP_DIR}/session-status"

cleanup() {
    local exit_code=$?

    if [[ -f "${TEMP_DIR}/ui.env.backup" ]]; then
        cp "${TEMP_DIR}/ui.env.backup" "${UI_ENV_FILE}"
    fi

    if [[ -f "${TEMP_DIR}/ui.package.json.backup" ]]; then
        cp "${TEMP_DIR}/ui.package.json.backup" "${UI_PACKAGE_JSON_FILE}"
    fi

    if [[ -f "${TEMP_DIR}/ui.config.ts.backup" ]]; then
        cp "${TEMP_DIR}/ui.config.ts.backup" "${UI_CONFIG_FILE}"
    fi

    if [[ -f "${TEMP_DIR}/ui.metrics-panel.tsx.backup" ]]; then
        cp "${TEMP_DIR}/ui.metrics-panel.tsx.backup" "${UI_METRICS_PANEL_FILE}"
    fi

    if [[ -f "${TEMP_DIR}/ui.dockerfile.backup" ]]; then
        cp "${TEMP_DIR}/ui.dockerfile.backup" "${UI_DOCKERFILE_FILE}"
    fi

    if [[ -f "${TEMP_DIR}/app.dockerfile.backup" ]]; then
        cp "${TEMP_DIR}/app.dockerfile.backup" "${APP_DOCKERFILE_FILE}"
    fi

    if [[ -f "${TEMP_DIR}/setup.sh.backup" ]]; then
        cp "${TEMP_DIR}/setup.sh.backup" "${SETUP_SCRIPT_FILE}"
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
  MODEL_DOWNLOAD_IMAGE       External model-download image to run without local build.
                             Default: intel/model-download:latest
  MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS
                             Max model-download job polling attempts for demo setup.sh patch.
                             Default: 240 (attempts every 5s).
  MODEL_DOWNLOAD_STATUS_LOG_EVERY
                             Print model-download job status at least every N attempts.
                             Default: 10.
  MODEL_DOWNLOAD_PULL_POLICY Pull policy for external model-download image.
                             Values: if-missing (default), always, never
  CHATQNA_LOG_DIR            Directory for tmux session logs.
                             Default: <chat-question-and-answer>/logs
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

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

install_gpg_keyring() {
    local url="$1"
    local output_path="$2"
    local temp_key_file="${TEMP_DIR}/$(basename "$output_path").asc"

    echo "Fetching GPG key: ${url}"
    curl -fsSL --retry 5 --retry-delay 2 --retry-connrefused "$url" -o "$temp_key_file"

    if ! grep -q "BEGIN PGP PUBLIC KEY BLOCK" "$temp_key_file"; then
        echo "Downloaded data from ${url} is not a valid ASCII-armored OpenPGP key." >&2
        echo "First lines of the response:" >&2
        head -n 5 "$temp_key_file" >&2 || true
        return 1
    fi

    sudo gpg --dearmor --yes -o "$output_path" "$temp_key_file"
    sudo chmod 644 "$output_path"
}

backup_file_if_needed() {
    local src="$1"
    local dst="$2"

    if [[ ! -f "$dst" ]]; then
        cp "$src" "$dst"
    fi
}

apply_demo_ui_build_patches() {
    echo "=== APPLYING DEMO-ONLY UI BUILD PATCHES (TEMPORARY) ==="

    backup_file_if_needed "${UI_PACKAGE_JSON_FILE}" "${TEMP_DIR}/ui.package.json.backup"
    backup_file_if_needed "${UI_CONFIG_FILE}" "${TEMP_DIR}/ui.config.ts.backup"
    backup_file_if_needed "${UI_METRICS_PANEL_FILE}" "${TEMP_DIR}/ui.metrics-panel.tsx.backup"
    backup_file_if_needed "${UI_DOCKERFILE_FILE}" "${TEMP_DIR}/ui.dockerfile.backup"
    backup_file_if_needed "${APP_DOCKERFILE_FILE}" "${TEMP_DIR}/app.dockerfile.backup"
    backup_file_if_needed "${SETUP_SCRIPT_FILE}" "${TEMP_DIR}/setup.sh.backup"

    python3 - "${UI_PACKAGE_JSON_FILE}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
deps = data.setdefault("dependencies", {})

required = {
    "chart.js": "^4.5.1",
    "react-chartjs-2": "^5.3.0",
    "react-markdown": "^10.1.0",
    "remark-gfm": "^4.0.1",
}

changed = False
for name, version in required.items():
    if deps.get(name) != version:
        deps[name] = version
        changed = True

if changed:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

    python3 - "${UI_CONFIG_FILE}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")

metrics_block = "export const METRICS_URL: string =\n  import.meta.env.VITE_BACKEND_SERVICE_ENDPOINT + '/metrics';\n"
system_info_block = "export const SYSTEM_INFO: string =\n  import.meta.env.VITE_SYSTEM_INFO || '';\n"

if "export const METRICS_URL" not in content:
    marker = "export const MODEL_URL: string ="
    if marker in content:
        content = content.replace(marker, metrics_block + marker, 1)

if "export const SYSTEM_INFO" not in content:
    content = content + "\n" + system_info_block

path.write_text(content, encoding="utf-8")
PY

    python3 - "${UI_METRICS_PANEL_FILE}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")

old = '  const value = points.at(-1)?.[key]\n'
new = '  const lastPoint = points.length > 0 ? points[points.length - 1] : undefined\n  const value = lastPoint?.[key]\n'

if old in content:
    content = content.replace(old, new, 1)

path.write_text(content, encoding="utf-8")
PY

    python3 - "${UI_DOCKERFILE_FILE}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")
content = content.replace('RUN ["npm", "ci"]', 'RUN npm ci || npm install --no-package-lock')
path.write_text(content, encoding="utf-8")
PY

    python3 - "${APP_DOCKERFILE_FILE}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")
content = content.replace(
    'RUN poetry config virtualenvs.create false && \\\n    poetry install --only main --no-root && \\\n    rm -rf ~/.cache',
    'RUN poetry config virtualenvs.create false && \\\n    poetry lock && \\\n    poetry install --only main --no-root && \\\n    rm -rf ~/.cache',
)
path.write_text(content, encoding="utf-8")
PY

    python3 - "${SETUP_SCRIPT_FILE}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")

content = content.replace(
    '    local MAX_ATTEMPTS=60\n',
    '    local MAX_ATTEMPTS="${MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS:-240}"\n',
    1,
)

content = content.replace(
    '    declare -A job_done\n    declare -A job_conversion_path\n',
    '    declare -A job_done\n    declare -A job_conversion_path\n    declare -A job_last_status\n\n    local status_log_every="${MODEL_DOWNLOAD_STATUS_LOG_EVERY:-10}"\n',
    1,
)

content = content.replace(
    '            echo "Job $job_id → $status"\n',
    '            if [[ "${job_last_status[$job_id]-}" != "$status" || $((attempt % status_log_every)) -eq 0 ]]; then\n                echo "Job $job_id → $status (attempt $attempt/$MAX_ATTEMPTS)"\n                job_last_status[$job_id]="$status"\n            fi\n',
    1,
)

content = content.replace(
    '                        download_ovms_model "$LLM_MODEL" "llm" "openvino"\n',
    '                        download_ovms_model "$LLM_MODEL" "llm" "openvino" || return 1\n',
    1,
)

content = content.replace(
    '                        download_ovms_model "$EMBEDDING_MODEL_NAME" "embeddings" "openvino"\n',
    '                        download_ovms_model "$EMBEDDING_MODEL_NAME" "embeddings" "openvino" || return 1\n',
    1,
)

content = content.replace(
    '        setup_inference "$LLM_SERVICE"\n        setup_embedding "$EMBED_SERVICE"\n',
    '        setup_inference "$LLM_SERVICE" || return 1\n        setup_embedding "$EMBED_SERVICE" || return 1\n',
    1,
)

path.write_text(content, encoding="utf-8")
PY
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

start_tmux_session_logged() {
    local session_name="$1"
    local working_dir="$2"
    local command="$3"
    local log_file="$4"
    local runner_file="${TEMP_DIR}/${session_name}.runner.sh"
    local status_file="${SESSION_STATUS_DIR}/${session_name}.status"
    local quoted_working_dir
    local quoted_log_file
    local quoted_status_file

    if tmux has-session -t "$session_name" 2>/dev/null; then
        echo "tmux session '$session_name' already exists. Close it first or attach to it:" >&2
        echo "tmux attach-session -t $session_name" >&2
        exit 1
    fi

    mkdir -p "$(dirname "$log_file")" "${SESSION_STATUS_DIR}"
    rm -f "$status_file"

    printf -v quoted_working_dir '%q' "$working_dir"
    printf -v quoted_log_file '%q' "$log_file"
    printf -v quoted_status_file '%q' "$status_file"

    cat > "$runner_file" <<EOF
#!/usr/bin/env bash
set -o pipefail
cd ${quoted_working_dir}
{
    echo "=== ${session_name} started at \$(date -Is) ==="
    ${command}
} 2>&1 | tee -a ${quoted_log_file}
status=\${PIPESTATUS[0]}
echo "\${status}" > ${quoted_status_file}
echo "=== ${session_name} exited with status \${status} at \$(date -Is) ===" | tee -a ${quoted_log_file}
if (( status != 0 )); then
    echo "Command failed. Log file: ${log_file}" | tee -a ${quoted_log_file}
    echo "Keeping this tmux session open for inspection. Press Ctrl-D to close it." | tee -a ${quoted_log_file}
    exec bash
fi
exit "\${status}"
EOF

    chmod +x "$runner_file"
    tmux new-session -d -s "$session_name" -c "$working_dir" "bash $(printf '%q' "$runner_file")"
}

ensure_tmux_session_running() {
    local session_name="$1"
    local wait_seconds="${2:-2}"
    local status_file="${SESSION_STATUS_DIR}/${session_name}.status"
    local log_file="${LOG_DIR}/${session_name}.log"
    local status

    sleep "$wait_seconds"

    if [[ -f "$status_file" ]]; then
        status="$(cat "$status_file")"
        if [[ "$status" != "0" ]]; then
            echo "ERROR: tmux session '${session_name}' command failed with status ${status}." >&2
            echo "Check log file: ${log_file}" >&2
            echo "Or attach to the kept-open session: tmux attach-session -t ${session_name}" >&2
            return 1
        fi
    fi

    if ! tmux has-session -t "$session_name" 2>/dev/null; then
        echo "ERROR: tmux session '${session_name}' exited unexpectedly." >&2
        echo "Check log file: ${log_file}" >&2
        return 1
    fi
}

write_runtime_env_file() {
    local key
    local value

    : > "${RUNTIME_ENV_FILE}"

    for key in \
        HUGGINGFACEHUB_API_TOKEN \
        LLM_MODEL \
        EMBEDDING_MODEL_NAME \
        RERANKER_MODEL \
        DEVICE \
        MODEL_DOWNLOAD_HOST \
        MODEL_DOWNLOAD_PORT \
        MODEL_DOWNLOAD_IMAGE \
        MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS \
        MODEL_DOWNLOAD_STATUS_LOG_EVERY \
        ALLOWED_HOSTS \
        REGISTRY \
        TAG \
        APP_METRICS_URL \
        HOST_IP \
        GETI_SERVER_SSL_VERIFY; do
        value="${!key-}"
        printf 'export %s=%q\n' "$key" "$value" >> "${RUNTIME_ENV_FILE}"
    done

    for key in http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY; do
        value="${!key-}"
        if [[ -n "$value" ]]; then
            printf 'export %s=%q\n' "$key" "$value" >> "${RUNTIME_ENV_FILE}"
        fi
    done

    chmod 600 "${RUNTIME_ENV_FILE}"
}

write_model_download_start_script() {
    local script_path="$1"
    local runtime_env_file="$2"
    local model_path="$3"
    local quoted_runtime_env_file
    local quoted_model_path

    printf -v quoted_runtime_env_file '%q' "$runtime_env_file"
    printf -v quoted_model_path '%q' "$model_path"

    cat > "$script_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

source ${quoted_runtime_env_file}

image="\${MODEL_DOWNLOAD_IMAGE:-intel/model-download:latest}"
pull_policy="\${MODEL_DOWNLOAD_PULL_POLICY:-if-missing}"
model_path=${quoted_model_path}
host_port="\${MODEL_DOWNLOAD_PORT:-8200}"

echo "Using external model-download image: \${image}"
echo "Using model-download pull policy: \${pull_policy}"
echo "Using model-download model path: \${model_path}"

docker rm -f model-download >/dev/null 2>&1 || true

case "\${pull_policy}" in
    always)
        docker pull "\${image}"
        ;;
    if-missing)
        if ! docker image inspect "\${image}" >/dev/null 2>&1; then
            docker pull "\${image}"
        else
            echo "Image already available locally, skipping pull."
        fi
        ;;
    never)
        if ! docker image inspect "\${image}" >/dev/null 2>&1; then
            echo "MODEL_DOWNLOAD_PULL_POLICY=never but image not found locally: \${image}" >&2
            exit 1
        fi
        ;;
    *)
        echo "Invalid MODEL_DOWNLOAD_PULL_POLICY: \${pull_policy}. Use: if-missing, always, never" >&2
        exit 1
        ;;
esac

docker run --rm \
    --name model-download \
    -p "\${host_port}:8000" \
    -v "\${model_path}:/opt/models" \
    --group-add "\$(id -g)" \
    -e no_proxy="\${no_proxy:-}" \
    -e http_proxy="\${http_proxy:-}" \
    -e https_proxy="\${https_proxy:-}" \
    -e NO_PROXY="\${NO_PROXY:-}" \
    -e HTTP_PROXY="\${HTTP_PROXY:-}" \
    -e HTTPS_PROXY="\${HTTPS_PROXY:-}" \
    -e HF_HUB_ENABLE_HF_TRANSFER=1 \
    -e HF_TOKEN="\${HUGGINGFACEHUB_API_TOKEN:-}" \
    -e HUGGINGFACEHUB_API_TOKEN="\${HUGGINGFACEHUB_API_TOKEN:-}" \
    -e MAX_UPLOAD_SIZE_MB="\${MAX_UPLOAD_SIZE_MB:-500}" \
    -e UPLOAD_CHUNK_SIZE_KB="\${UPLOAD_CHUNK_SIZE_KB:-8}" \
    -e ENABLED_PLUGINS=all \
    -e MODEL_PATH="\${model_path}" \
    -e OVMS_RELEASE_TAG="\${OVMS_RELEASE_TAG:-v2025.4.1}" \
    -e GETI_HOST="\${GETI_HOST:-}" \
    -e GETI_TOKEN="\${GETI_TOKEN:-}" \
    -e GETI_WORKSPACE_ID="\${GETI_WORKSPACE_ID:-}" \
    -e GETI_SERVER_API_VERSION="\${GETI_SERVER_API_VERSION:-v1}" \
    -e GETI_SERVER_SSL_VERIFY="\${GETI_SERVER_SSL_VERIFY:-False}" \
    "\${image}" \
    --plugins all
EOF

    chmod +x "$script_path"
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
    local elapsed
    local last_diag_ts
    local container_status
    local log_file="${LOG_DIR}/model_download.log"

    start_ts="$(date +%s)"
    last_diag_ts=0

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

        elapsed=$(( $(date +%s) - start_ts ))

        if (( elapsed - last_diag_ts >= 10 )); then
            container_status="$(run_docker_cmd "docker ps --filter name=^/model-download$ --format '{{.Status}}'")"
            if [[ -z "$container_status" ]]; then
                echo "model-download container is not running yet (image pull/start may still be in progress)."
            else
                echo "model-download container status: $container_status"
            fi

            if [[ -f "$log_file" ]]; then
                echo "last model_download tmux log lines:"
                tail -n 5 "$log_file" || true
            fi

            last_diag_ts=$elapsed
        fi

        if (( $(date +%s) - start_ts >= timeout_seconds )); then
            echo "Timed out waiting for model-download health endpoint: $url" >&2
            echo "Check tmux/session logs: ${log_file}" >&2
            return 1
        fi

        echo "waiting for model-download health..."
        sleep 1
    done
}

wait_for_metrics_manager_health() {
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

raise SystemExit(0 if data.get("status") == "healthy" else 1)
PY
        then
            return 0
        fi

        if (( $(date +%s) - start_ts >= timeout_seconds )); then
            echo "Timed out waiting for metrics-manager health endpoint: $url" >&2
            return 1
        fi

        echo "waiting for metrics-manager health..."
        sleep 1
    done
}

wait_for_http_content() {
    local url="$1"
    local timeout_seconds="$2"
    local label="$3"
    local expected_substring="${4:-}"
    local start_ts
    local response

    start_ts="$(date +%s)"

    while true; do
        response="$(curl -fsS "$url" 2>/dev/null || true)"

        if [[ -n "$response" ]]; then
            if [[ -z "$expected_substring" ]] || [[ "$response" == *"$expected_substring"* ]]; then
                return 0
            fi
        fi

        if (( $(date +%s) - start_ts >= timeout_seconds )); then
            echo "Timed out waiting for ${label}: $url" >&2
            return 1
        fi

        echo "waiting for ${label}..."
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
    export MODEL_DOWNLOAD_IMAGE="${MODEL_DOWNLOAD_IMAGE}"
    export MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS="${MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS}"
    export MODEL_DOWNLOAD_STATUS_LOG_EVERY="${MODEL_DOWNLOAD_STATUS_LOG_EVERY}"
    export ALLOWED_HOSTS="*"
    export REGISTRY="intel/"
    export TAG=latest
    export APP_METRICS_URL="http://$ip:8100/metrics"
    export HOST_IP="$ip"
    export GETI_SERVER_SSL_VERIFY=False
}

install_dependencies() {
    local need_apt_update=false
    local need_chrome_install=false
    local need_docker_install=false
    local need_tmux_install=false
    local need_base_packages_install=false

    if command_exists google-chrome || command_exists google-chrome-stable; then
        echo "=== GOOGLE CHROME ALREADY INSTALLED: SKIPPING INSTALL ==="
    else
        need_chrome_install=true
        need_base_packages_install=true
        echo "=== CONFIGURING GOOGLE CHROME REPOSITORY ==="
        sudo install -m 0755 -d /etc/apt/keyrings
        install_gpg_keyring "https://dl.google.com/linux/linux_signing_key.pub" "/etc/apt/keyrings/google-chrome.gpg"
        sudo tee /etc/apt/sources.list.d/google-chrome.list > /dev/null <<'EOF'
deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main
EOF
        need_apt_update=true
    fi

    if command_exists docker; then
        echo "=== DOCKER ALREADY INSTALLED: SKIPPING INSTALL ==="
    else
        need_docker_install=true
        need_base_packages_install=true
        echo "=== CONFIGURING DOCKER REPOSITORY ==="
        sudo install -m 0755 -d /etc/apt/keyrings
        install_gpg_keyring "https://download.docker.com/linux/ubuntu/gpg" "/etc/apt/keyrings/docker.gpg"
        echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        need_apt_update=true
    fi

    if command_exists tmux; then
        echo "=== TMUX ALREADY INSTALLED: SKIPPING INSTALL ==="
    else
        need_tmux_install=true
        need_base_packages_install=true
    fi

    if ! command_exists curl || ! command_exists gpg || ! command_exists git || ! command_exists jq || ! command_exists yq || ! command_exists python3 || ! command_exists pip3; then
        need_base_packages_install=true
    fi

    if [[ "$need_apt_update" == "true" ]]; then
        echo "=== UPDATING PACKAGE INDEX ==="
        sudo apt update
    fi

    if [[ "$need_base_packages_install" == "true" ]]; then
        echo "=== INSTALLING BASE DEPENDENCIES ==="
        sudo apt install -y ca-certificates curl gnupg git jq yq intel-gpu-tools python3-poetry python3-venv python3-pip
    else
        echo "=== BASE DEPENDENCIES ALREADY AVAILABLE: SKIPPING INSTALL ==="
    fi

    if [[ "$need_chrome_install" == "true" ]]; then
        echo "=== INSTALLING GOOGLE CHROME ==="
        sudo apt install -y google-chrome-stable
    fi

    if [[ "$need_docker_install" == "true" ]]; then
        echo "=== INSTALLING DOCKER ==="
        sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        sudo usermod -aG docker "$USER"
        sudo chown root:docker /var/run/docker.sock
        sudo chmod 660 /var/run/docker.sock
    fi

    if [[ "$need_tmux_install" == "true" ]]; then
        echo "=== INSTALLING TMUX ==="
        sudo apt install -y tmux
    fi
}

main() {
    parse_args "$@"

    if command -v tput >/dev/null 2>&1; then
        tput clear || true
    fi

    require_file "${COMPOSE_FILE}"
    require_file "${UI_ENV_FILE}"
    require_file "${UI_PACKAGE_JSON_FILE}"
    require_file "${UI_CONFIG_FILE}"
    require_file "${UI_METRICS_PANEL_FILE}"
    require_file "${UI_DOCKERFILE_FILE}"
    require_file "${APP_DOCKERFILE_FILE}"
    require_file "${SETUP_SCRIPT_FILE}"

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
    write_runtime_env_file
    apply_demo_ui_build_patches
    mkdir -p "${MODEL_DOWNLOAD_MODEL_PATH}"
    mkdir -p "${LOG_DIR}"

    restart_existing_runtime_if_needed

    cp "${UI_ENV_FILE}" "${TEMP_DIR}/ui.env.backup"

    echo "Using target device: ${DEVICE}"
    echo "Using host IP: ${ip}"
    echo "Using model-download host path: ${MODEL_DOWNLOAD_MODEL_PATH}"
    echo "Writing tmux logs to: ${LOG_DIR}"

    local runtime_env_file_quoted
    local model_download_start_script="${TEMP_DIR}/start_model_download.sh"
    local model_download_start_script_quoted
    printf -v runtime_env_file_quoted '%q' "${RUNTIME_ENV_FILE}"
    printf -v model_download_start_script_quoted '%q' "${model_download_start_script}"
    write_model_download_start_script "${model_download_start_script}" "${RUNTIME_ENV_FILE}" "${MODEL_DOWNLOAD_MODEL_PATH}"

    echo " === STARTING METRICS_SERVER CONTAINER ==="

    start_tmux_session_logged \
        "metrics-manager" \
        "${APP_ROOT}" \
        "sg docker -c 'docker run --rm --privileged --name metrics-manager --device /dev/dri -p 9090:9090 -p 9273:9273 -v /sys:/sys:ro -v /run:/run:ro --pid host intel/metrics-manager:2026.1.0-20260508-weekly'" \
        "${LOG_DIR}/metrics-manager.log"

echo "=== STARTING MODEL DOWNLOAD MICROSERVICE (REQUIRED TO DOWNLOAD TARGET_MODEL) ==="
echo "--> To attach to model download TMUX session type: tmux attach-session -t model_download"
    start_tmux_session_logged \
        "model_download" \
        "${APP_ROOT}" \
        "sg docker -c 'bash ${model_download_start_script_quoted}'" \
        "${LOG_DIR}/model_download.log"

    ensure_tmux_session_running "metrics-manager" 2
    ensure_tmux_session_running "model_download" 2

echo "=== CONTAINERS STARTED IN THE BACKGROUND, WAITING FOR API HEALTHY MESSAGE ==="
    wait_for_metrics_manager_health "http://localhost:9090/health" "${MAX_WAIT_SECONDS}"
    wait_for_http_content "http://localhost:9273/metrics" "${MAX_WAIT_SECONDS}" "metrics-manager Prometheus exporter" "gpu_engine_usage_usage"
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
    start_tmux_session_logged \
        "chatqna" \
        "${APP_ROOT}" \
        "bash -lc 'source ${runtime_env_file_quoted}; source setup.sh llm=OVMS embed=OVMS; if [[ -f ovms/OpenVINO/gpt-oss-20b-int4-ov/chat_template.ninja ]]; then sed -i '\''s/{- \"<|start|>assistant\" }}/{- \"<|start|>assistant<|channel|>final<|message|>\" }}/g'\'' ovms/OpenVINO/gpt-oss-20b-int4-ov/chat_template.ninja; else echo \"WARNING: chat template not found, skipping tuning\" >&2; fi; sg docker -c \"docker compose up --build\"'" \
        "${LOG_DIR}/chatqna.log"

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
