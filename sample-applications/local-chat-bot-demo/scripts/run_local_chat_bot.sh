#!/usr/bin/env bash
# Local Chat Bot demo launcher.
#
# Starts the whole demo stack in the background:
#   metrics-manager  -> host telemetry (CPU/GPU/NPU)          [docker run -d]
#   model-download   -> downloads and converts the OVMS models [docker run -d]
#   ChatQnA stack    -> pristine sample app + demo overlay     [docker compose up -d]
#   autorun.py       -> side-by-side prompt submission tool    [foreground, optional]
#
# The sample application sources are NEVER modified: everything runs from the
# working copy created by scripts/prepare_workspace.sh.
#
# Converted models live in a persistent cache (see OVMS_MODELS_DIR in demo.env),
# so restarting the demo never re-downloads them.

set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEMO_ROOT}/scripts/lib.sh"

RESTART=true
CLEAN_WORKSPACE=false
STRICT_BASELINE=false
SKIP_INSTALL=false
SKIP_PREPARE=false
RUN_AUTORUN=true
RECONFIGURE=false
AUTORUN_ARGS=()
TARGET_DEVICE="${CHATQNA_TARGET_DEVICE:-${DEVICE:-}}"
HF_TOKEN_OVERRIDE="${HUGGINGFACEHUB_API_TOKEN:-}"

usage() {
    cat <<'EOF'
Usage: ./scripts/run_local_chat_bot.sh [options]

Options:
  --no-restart          Keep already running demo containers (default: restart them).
  --clean               Recreate the working copy from scratch (use after editing
                        overlay/, patches/ or generators/). Converted models are kept.
  --strict              Fail if upstream drifted from the recorded baseline.
  --device CPU|GPU      Target device for OVMS conversion/inference.
  --hf-token <token>    Hugging Face API token (only needed while models are
                        still missing from the cache).
  --reconfigure         Ask for the device again and overwrite the saved answer.
  --skip-install        Do not run scripts/install_prereqs.sh.
  --skip-prepare        Reuse the existing working copy as-is.
  --no-autorun          Do not start the prompt submission tool at the end.
  --cli                 Read prompts from the terminal instead of the browser console.
  --reset-chatgpt-profile
                        Drop the saved ChatGPT login before starting the browsers.
  --help, -h            Show this message.

The device is asked for once and stored in the file named by DEMO_CONFIG_FILE
(scripts/demo.env). The Hugging Face token is never stored: it is only needed to
download the models, so once they are in the cache it is not asked for again.
An unattended start (e.g. at boot) therefore runs without any input.
Precedence: command line > environment > saved answer.

Restarting is safe: downloaded/converted models live in a persistent cache and
are reused (see OVMS_MODELS_DIR in scripts/demo.env).

Logs:
  docker logs -f model-download
  docker logs -f metrics-manager
  ./scripts/logs.sh            # ChatQnA stack
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --no-restart) RESTART=false ;;
            --force-restart|-f) RESTART=true ;;   # kept for backwards compatibility
            --clean) CLEAN_WORKSPACE=true ;;
            --strict) STRICT_BASELINE=true ;;
            --skip-install) SKIP_INSTALL=true ;;
            --skip-prepare) SKIP_PREPARE=true ;;
            --no-autorun) RUN_AUTORUN=false ;;
            --reconfigure) RECONFIGURE=true ;;
            --cli) AUTORUN_ARGS+=(--cli) ;;
            --reset-chatgpt-profile) AUTORUN_ARGS+=(--reset-chatgpt-profile) ;;
            --device)
                shift; [[ $# -gt 0 ]] || { echo "Missing value for --device" >&2; usage >&2; exit 1; }
                TARGET_DEVICE="$1" ;;
            --hf-token)
                shift; [[ $# -gt 0 ]] || { echo "Missing value for --hf-token" >&2; usage >&2; exit 1; }
                HF_TOKEN_OVERRIDE="$1" ;;
            --help|-h) usage; exit 0 ;;
            *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
        esac
        shift
    done
}

validate_device() {
    case "${1^^}" in
        CPU|GPU) return 0 ;;
        NPU)
            echo "NPU is not implemented by the ChatQnA sample application." >&2
            return 1 ;;
        *) return 1 ;;
    esac
}

load_saved_answers() {
    if [[ "${RECONFIGURE}" == "true" ]]; then
        TARGET_DEVICE=""
        return 0
    fi
    [[ -f "${DEMO_CONFIG_FILE}" ]] || return 0

    # Loaded into a dedicated name, so that a value given on the command line or
    # exported into the environment still wins over the saved answer.
    # shellcheck disable=SC1090
    source "${DEMO_CONFIG_FILE}"
    [[ -n "${TARGET_DEVICE}" ]] || TARGET_DEVICE="${SAVED_DEVICE:-}"
    info "Using the saved configuration: ${DEMO_CONFIG_FILE}"
}

save_answers() {
    mkdir -p "$(dirname "${DEMO_CONFIG_FILE}")"
    {
        echo "# Local Chat Bot demo - answer from the first run, reused on every later"
        echo "# start so that the demo can come up unattended. Rewritten by --reconfigure."
        echo "# The Hugging Face token is deliberately NOT stored here."
        printf 'SAVED_DEVICE=%q\n' "${TARGET_DEVICE}"
    } > "${DEMO_CONFIG_FILE}.tmp"
    mv "${DEMO_CONFIG_FILE}.tmp" "${DEMO_CONFIG_FILE}"
    info "Configuration saved: ${DEMO_CONFIG_FILE}"
}

require_terminal() {
    [[ -t 0 ]] || die "$1 is not configured and there is no terminal to ask on. Run \
${DEMO_ROOT}/scripts/run_local_chat_bot.sh once interactively (or pass --hf-token/--device)."
}

models_are_cached() {
    # setup.sh copies every converted model to ${VOLUME_OVMS}/models/<model name>.
    local model
    for model in "${LLM_MODEL}" "${EMBEDDING_MODEL_NAME}"; do
        [[ -n "$(find "${OVMS_MODELS_DIR}/models/${model}" -mindepth 1 -print -quit 2>/dev/null)" ]] \
            || return 1
    done
}

prompt_for_token_if_needed() {
    [[ -z "${HF_TOKEN_OVERRIDE}" ]] || return 0
    # The token is only used to download the models, so a cached model set makes
    # it unnecessary - this is what lets the demo start unattended.
    if models_are_cached; then
        info "Models already converted in ${OVMS_MODELS_DIR} - no Hugging Face token needed."
        return 0
    fi

    require_terminal "Hugging Face API token"
    read -r -p "Provide a HuggingFace API token for model download: " HF_TOKEN_OVERRIDE
    [[ -n "${HF_TOKEN_OVERRIDE}" ]] || die "Hugging Face API token cannot be empty."
}

prompt_for_device_if_needed() {
    while true; do
        if [[ -z "${TARGET_DEVICE}" ]]; then
            require_terminal "Target device"
            read -r -p "Please enter a target device (CPU, GPU): " TARGET_DEVICE
        fi
        TARGET_DEVICE="${TARGET_DEVICE^^}"
        if validate_device "${TARGET_DEVICE}"; then
            info "Target device: ${TARGET_DEVICE}"
            break
        fi
        echo "Invalid input. Please enter one of: CPU, GPU"
        TARGET_DEVICE=""
    done
}

host_ip_candidate() {
    local ip=""
    # `hostname -I` prints nothing at all until an address is assigned, and it is
    # not installed everywhere, so `ip route get` is tried first.
    if command_exists ip; then
        ip="$(ip -4 route get 1.1.1.1 2>/dev/null \
            | awk '{ for (i = 1; i < NF; i++) if ($i == "src") { print $(i + 1); exit } }')"
    fi
    if [[ -z "${ip}" ]] && command_exists hostname; then
        ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    fi
    echo "${ip}"
}

detect_host_ip() {
    local ip deadline
    deadline=$(( $(date +%s) + HOST_IP_WAIT_SECONDS ))
    while true; do
        ip="$(host_ip_candidate)"
        if [[ -n "${ip}" && "${ip}" != 127.* ]]; then
            echo "${ip}"
            return 0
        fi
        (( $(date +%s) < deadline )) || return 1
        echo "waiting for a host IP address..." >&2
        sleep 2
    done
}

configure_runtime_env() {
    local ip="$1"

    export HUGGINGFACEHUB_API_TOKEN="${HF_TOKEN_OVERRIDE}"
    export LLM_MODEL EMBEDDING_MODEL_NAME RERANKER_MODEL
    export DEVICE="${TARGET_DEVICE}"
    export MODEL_DOWNLOAD_HOST="${ip}"
    export MODEL_DOWNLOAD_PORT MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS MODEL_DOWNLOAD_STATUS_LOG_EVERY
    export ALLOWED_HOSTS="*"
    # REGISTRY/TAG are still needed for the images the demo does not build itself.
    export REGISTRY="intel/"
    export TAG="latest"
    export APP_METRICS_URL="http://${ip}:8100/metrics"
    export HOST_IP="${ip}"
    export GETI_SERVER_SSL_VERIFY=False
    export DEMO_BE_IMAGE DEMO_UI_IMAGE
    export COMPOSE_PROJECT_NAME
    # Persistent model cache - consumed by the patched setup.sh and by compose.
    export VOLUME_OVMS="${OVMS_MODELS_DIR}"
    # Consumed by tools/autorun.py.
    export PROMPT_CONSOLE_PORT PROMPT_CONSOLE_HEIGHT_PCT CHATGPT_PROFILE_DIR
}

start_metrics_manager() {
    run_docker_cmd "docker rm -f metrics-manager >/dev/null 2>&1 || true"
    run_docker_cmd "docker run -d --restart unless-stopped --privileged \
        --name metrics-manager \
        --device /dev/dri \
        -p 9090:9090 -p 9273:9273 \
        -v /sys:/sys:ro -v /run:/run:ro \
        --pid host \
        $(printf '%q' "${METRICS_MANAGER_IMAGE}") >/dev/null"
}

pull_model_download_image_if_needed() {
    case "${MODEL_DOWNLOAD_PULL_POLICY}" in
        always)
            run_docker_cmd "docker pull $(printf '%q' "${MODEL_DOWNLOAD_IMAGE}")"
            ;;
        if-missing)
            if ! run_docker_cmd "docker image inspect $(printf '%q' "${MODEL_DOWNLOAD_IMAGE}") >/dev/null 2>&1"; then
                run_docker_cmd "docker pull $(printf '%q' "${MODEL_DOWNLOAD_IMAGE}")"
            else
                info "model-download image already available locally"
            fi
            ;;
        never)
            run_docker_cmd "docker image inspect $(printf '%q' "${MODEL_DOWNLOAD_IMAGE}") >/dev/null 2>&1" \
                || die "MODEL_DOWNLOAD_PULL_POLICY=never but image not found locally: ${MODEL_DOWNLOAD_IMAGE}"
            ;;
        *)
            die "Invalid MODEL_DOWNLOAD_PULL_POLICY: ${MODEL_DOWNLOAD_PULL_POLICY}. Use: if-missing, always, never"
            ;;
    esac
}

start_model_download() {
    pull_model_download_image_if_needed
    run_docker_cmd "docker rm -f model-download >/dev/null 2>&1 || true"
    run_docker_cmd "docker run -d \
        --name model-download \
        -p $(printf '%q' "${MODEL_DOWNLOAD_PORT}"):8000 \
        -v $(printf '%q' "${MODEL_DOWNLOAD_MODEL_PATH}"):/opt/models \
        --group-add \$(id -g) \
        -e no_proxy=$(printf '%q' "${no_proxy:-}") \
        -e http_proxy=$(printf '%q' "${http_proxy:-}") \
        -e https_proxy=$(printf '%q' "${https_proxy:-}") \
        -e NO_PROXY=$(printf '%q' "${NO_PROXY:-}") \
        -e HTTP_PROXY=$(printf '%q' "${HTTP_PROXY:-}") \
        -e HTTPS_PROXY=$(printf '%q' "${HTTPS_PROXY:-}") \
        -e HF_HUB_ENABLE_HF_TRANSFER=1 \
        -e HF_TOKEN=$(printf '%q' "${HUGGINGFACEHUB_API_TOKEN}") \
        -e HUGGINGFACEHUB_API_TOKEN=$(printf '%q' "${HUGGINGFACEHUB_API_TOKEN}") \
        -e MAX_UPLOAD_SIZE_MB=${MAX_UPLOAD_SIZE_MB:-500} \
        -e UPLOAD_CHUNK_SIZE_KB=${UPLOAD_CHUNK_SIZE_KB:-8} \
        -e ENABLED_PLUGINS=$(printf '%q' "${MODEL_DOWNLOAD_PLUGINS}") \
        -e MODEL_PATH=$(printf '%q' "${MODEL_DOWNLOAD_MODEL_PATH}") \
        -e OVMS_RELEASE_TAG=$(printf '%q' "${OVMS_RELEASE_TAG:-v2025.4.1}") \
        -e GETI_SERVER_SSL_VERIFY=False \
        $(printf '%q' "${MODEL_DOWNLOAD_IMAGE}") \
        --plugins $(printf '%q' "${MODEL_DOWNLOAD_PLUGINS}") >/dev/null"
}

json_status_is() {
    local response="$1"
    local expected="$2"
    python3 - "${response}" "${expected}" <<'PY'
import json, sys
try:
    data = json.loads(sys.argv[1])
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if data.get("status") == sys.argv[2] else 1)
PY
}

wait_for_json_status() {
    local url="$1" timeout_seconds="$2" expected="$3" label="$4" container="${5:-}"
    local start_ts response elapsed last_diag_ts=0
    start_ts="$(date +%s)"

    while true; do
        response="$(curl -fsS "${url}" 2>/dev/null || true)"
        if [[ -n "${response}" ]] && json_status_is "${response}" "${expected}"; then
            return 0
        fi

        elapsed=$(( $(date +%s) - start_ts ))
        if [[ -n "${container}" ]] && (( elapsed - last_diag_ts >= 15 )); then
            info "${container}: $(run_docker_cmd "docker ps -a --filter name=^/${container}\$ --format '{{.Status}}'" || echo "not created")"
            last_diag_ts=${elapsed}
        fi

        if (( elapsed >= timeout_seconds )); then
            echo "Timed out waiting for ${label}: ${url}" >&2
            [[ -n "${container}" ]] && echo "Check logs with: docker logs --tail 100 ${container}" >&2
            return 1
        fi

        echo "waiting for ${label}..."
        sleep 1
    done
}

wait_for_http_content() {
    local url="$1" timeout_seconds="$2" label="$3" expected_substring="${4:-}"
    local start_ts response
    start_ts="$(date +%s)"

    while true; do
        response="$(curl -fsS "${url}" 2>/dev/null || true)"
        if [[ -n "${response}" ]] && { [[ -z "${expected_substring}" ]] || [[ "${response}" == *"${expected_substring}"* ]]; }; then
            return 0
        fi
        if (( $(date +%s) - start_ts >= timeout_seconds )); then
            echo "Timed out waiting for ${label}: ${url}" >&2
            return 1
        fi
        echo "waiting for ${label}..."
        sleep 1
    done
}

wait_for_chatqna_health() {
    local url="$1" timeout_seconds="$2"
    local start_ts response
    start_ts="$(date +%s)"

    while true; do
        response="$(curl -fsS "${url}" 2>/dev/null || true)"
        if [[ -n "${response}" ]] && python3 - "${response}" <<'PY'
import json, sys
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
            echo "Timed out waiting for ChatQnA health endpoint: ${url}" >&2
            echo "Inspect the stack with: ${DEMO_ROOT}/scripts/logs.sh" >&2
            echo "Re-running the demo is cheap - converted models are cached in ${OVMS_MODELS_DIR}" >&2
            return 1
        fi

        echo "waiting for ChatQnA health..."
        sleep 1
    done
}

stop_existing_runtime() {
    log "STOPPING EXISTING DEMO RUNTIME (models are kept)"
    "${DEMO_ROOT}/scripts/stop_local_chat_bot.sh" --quiet
}

main() {
    parse_args "$@"

    if [[ "${SKIP_INSTALL}" == "false" ]]; then
        "${DEMO_ROOT}/scripts/install_prereqs.sh"
    fi

    require_cmd curl
    require_cmd docker
    require_cmd jq
    require_cmd python3

    log "CONFIGURATION"
    load_saved_answers
    prompt_for_token_if_needed
    prompt_for_device_if_needed
    save_answers

    local ip
    ip="$(detect_host_ip)" || die "Could not determine the host IP address within \
${HOST_IP_WAIT_SECONDS}s. Started at boot, the demo can run before the network is up - \
raise HOST_IP_WAIT_SECONDS in scripts/demo.env if the machine needs longer."

    configure_runtime_env "${ip}"

    if [[ "${SKIP_PREPARE}" == "false" ]]; then
        local prepare_args=(--metrics-url "http://${ip}:8100/metrics")
        [[ "${CLEAN_WORKSPACE}" == "true" ]] && prepare_args+=(--clean)
        [[ "${STRICT_BASELINE}" == "true" ]] && prepare_args+=(--strict)
        "${DEMO_ROOT}/scripts/prepare_workspace.sh" "${prepare_args[@]}"
    fi
    require_workspace

    mkdir -p "${MODEL_DOWNLOAD_MODEL_PATH}" "${LOG_DIR}" "${OVMS_MODELS_DIR}"

    [[ "${RESTART}" == "true" ]] && stop_existing_runtime

    info "Host IP: ${ip}"
    info "Working copy: ${WORK_DIR}"
    info "Model cache (persistent): ${OVMS_MODELS_DIR}"
    info "model-download host path: ${MODEL_DOWNLOAD_MODEL_PATH}"

    log "STARTING METRICS-MANAGER"
    start_metrics_manager

    log "STARTING MODEL-DOWNLOAD MICROSERVICE"
    start_model_download

    log "WAITING FOR SUPPORTING SERVICES"
    wait_for_json_status "http://localhost:9090/health" "${MAX_WAIT_SECONDS}" "healthy" "metrics-manager health" "metrics-manager"
    wait_for_http_content "http://localhost:9273/metrics" "${MAX_WAIT_SECONDS}" "metrics-manager Prometheus exporter" "gpu_engine_usage_usage"
    wait_for_json_status "http://localhost:${MODEL_DOWNLOAD_PORT}/health" "${MAX_WAIT_SECONDS}" "ok" "model-download health" "model-download"

    log "PREPARING MODELS (CACHED MODELS ARE REUSED)"
    cd "${WORK_DIR}"
    # setup.sh exports the whole stack configuration and downloads/converts models.
    # It must be sourced, and it is not written for `set -euo pipefail`
    # (unset optional variables, `return 1` error handling), so strict mode is
    # temporarily relaxed. Failures are propagated by the demo generator patch.
    local setup_rc=0
    set +e +u
    # shellcheck disable=SC1091
    source ./setup.sh llm=OVMS embed=OVMS
    setup_rc=$?
    set -e -u
    (( setup_rc == 0 )) || die "setup.sh failed (exit ${setup_rc}) - see the output above."

    log "TUNING CHAT TEMPLATE"
    bash "${DEMO_ROOT}/generators/tune_chat_template.sh" "${VOLUME_OVMS}" "${LLM_MODEL}"

    log "STARTING CHATQNA STACK"
    run_docker_cmd "docker compose -f $(printf '%q' "${WORK_DIR}/docker-compose.yaml") -f $(printf '%q' "$(demo_compose_file)") up -d --build"

    log "WAITING FOR CHATQNA HEALTH (MODEL LOADING CAN TAKE SEVERAL MINUTES)"
    wait_for_chatqna_health "http://localhost:8100/health" "${MAX_WAIT_SECONDS}"

    log "DEMO IS UP"
    info "UI:      http://localhost:8101"
    info "Backend: http://localhost:8100/health"
    info "Logs:    ${DEMO_ROOT}/scripts/logs.sh"
    info "Stop:    ${DEMO_ROOT}/scripts/stop_local_chat_bot.sh"

    if [[ "${RUN_AUTORUN}" == "true" ]]; then
        log "STARTING PROMPT SUBMISSION TOOL"
        cd "${DEMO_ROOT}/tools"
        python3 -m venv .venv
        # shellcheck disable=SC1091
        source .venv/bin/activate
        pip install -q -r requirements.txt
        python3 autorun.py "${AUTORUN_ARGS[@]+"${AUTORUN_ARGS[@]}"}"
    fi
}

main "$@"

