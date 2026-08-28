#!/usr/bin/env bash
# Build the demo working copy of the ChatQnA sample application.
#
#   pristine sample app  ->  .work/chat-question-and-answer
#                            + overlay/   (full-file demo sources)
#                            + patches/   (git apply --3way)
#                            + generators/(idempotent tweaks)
#
# The sample application inside the repository is never modified.

set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEMO_ROOT}/scripts/lib.sh"

CLEAN=false
STRICT=false
METRICS_URL="${DEMO_METRICS_URL:-/v1/chatqna/metrics}"

usage() {
    cat <<'EOF'
Usage: ./scripts/prepare_workspace.sh [--clean] [--strict] [--metrics-url URL]

  --clean         Remove the existing working copy before recreating it.
                  Required after changing overlay/, patches/ or generators/.
  --strict        Fail (instead of warn) when upstream drifted from the baseline.
  --metrics-url   Value baked into VITE_METRICS_SERVICE_ENDPOINT.
  --help          Show this message.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --clean) CLEAN=true ;;
        --strict) STRICT=true ;;
        --metrics-url) shift; [[ $# -gt 0 ]] || die "Missing value for --metrics-url"; METRICS_URL="$1" ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
    shift
done

require_cmd git
require_cmd python3
require_cmd tar

fetch_sources() {
    mkdir -p "${WORK_ROOT}"

    if [[ -d "${APP_SOURCE_DIR}" ]] && git -C "${REPO_ROOT}" rev-parse --git-dir >/dev/null 2>&1; then
        info "Source: local repository (${APP_REL_PATH} @ HEAD)"
        git -C "${REPO_ROOT}" archive --format=tar HEAD -- "${APP_REL_PATH}" \
            | tar -x -C "${WORK_ROOT}" --strip-components=1
        return 0
    fi

    warn "Local sample application not available, falling back to a sparse clone."
    info "Source: ${UPSTREAM_REPO_URL} @ ${UPSTREAM_REF}"
    local clone_dir="${WORK_ROOT}/.upstream"
    rm -rf "${clone_dir}"
    git clone --filter=blob:none --no-checkout "${UPSTREAM_REPO_URL}" "${clone_dir}"
    git -C "${clone_dir}" sparse-checkout set --no-cone "${APP_REL_PATH}"
    git -C "${clone_dir}" checkout "${UPSTREAM_REF}"
    cp -a "${clone_dir}/${APP_REL_PATH}" "${WORK_DIR}"
    rm -rf "${clone_dir}"
}

snapshot_baseline() {
    # A throwaway git repo makes `git apply --3way` possible and lets you inspect
    # every demo modification with: git -C .work/chat-question-and-answer diff
    git -C "${WORK_DIR}" init -q
    git -C "${WORK_DIR}" -c user.email=demo@local -c user.name="Local Chat Bot demo" \
        -c commit.gpgsign=false add -A
    git -C "${WORK_DIR}" -c user.email=demo@local -c user.name="Local Chat Bot demo" \
        -c commit.gpgsign=false commit -q -m "Pristine sample application (baseline)"
}

check_baseline_drift() {
    local args=(check
        --overlay "${DEMO_ROOT}/overlay"
        --root "${WORK_DIR}"
        --file "${DEMO_ROOT}/overlay/MANIFEST.sha256")
    [[ "${STRICT}" == "true" ]] && args+=(--strict)
    python3 "${DEMO_ROOT}/generators/manifest.py" "${args[@]}"
}

apply_overlay() {
    tar -C "${DEMO_ROOT}/overlay" --exclude=MANIFEST.sha256 -cf - . | tar -x -C "${WORK_DIR}"
    info "Overlay files copied"
}

apply_patches() {
    shopt -s nullglob
    local patch
    for patch in "${DEMO_ROOT}"/patches/*.patch; do
        info "Applying $(basename "${patch}")"
        if ! git -C "${WORK_DIR}" apply --3way --whitespace=nowarn "${patch}"; then
            die "Failed to apply $(basename "${patch}"). Upstream drifted - refresh it with scripts/make_patches.sh"
        fi
    done
    shopt -u nullglob
}

apply_generators() {
    python3 "${DEMO_ROOT}/generators/gen_setup_sh.py" \
        --file "${WORK_DIR}/setup.sh" \
        --max-tokens "${DEMO_MAX_TOKENS}" \
        --job-max-attempts "${MODEL_DOWNLOAD_JOB_MAX_ATTEMPTS}" \
        --status-log-every "${MODEL_DOWNLOAD_STATUS_LOG_EVERY}"

    python3 "${DEMO_ROOT}/generators/gen_dockerfiles.py" --work-dir "${WORK_DIR}"

    python3 "${DEMO_ROOT}/generators/gen_ui_config.py" \
        --work-dir "${WORK_DIR}" \
        --metrics-url "${METRICS_URL}" \
        --system-info "${SYSTEM_INFO_TEXT}" \
        --max-tokens "${DEMO_MAX_TOKENS}"

    python3 "${DEMO_ROOT}/generators/gen_ui_deps.py" --work-dir "${WORK_DIR}"
}

preserve_converted_models() {
    # Older demo runs (and the upstream default) keep converted OVMS models inside
    # the working copy.  Move them to the persistent cache so that recreating the
    # workspace never re-downloads a 20B model.
    local legacy_dir="${WORK_DIR}/ovms"

    mkdir -p "${OVMS_MODELS_DIR}"

    if [[ -d "${legacy_dir}" ]] && find "${legacy_dir}" -mindepth 1 -print -quit >/dev/null 2>&1; then
        info "Migrating converted models to the persistent cache: ${OVMS_MODELS_DIR}"
        cp -an "${legacy_dir}/." "${OVMS_MODELS_DIR}/" 2>/dev/null || \
            cp -rn "${legacy_dir}/." "${OVMS_MODELS_DIR}/" 2>/dev/null || \
            warn "Could not migrate ${legacy_dir} (continuing, models may be re-downloaded)"
    fi
}

main() {
    if [[ -d "${WORK_DIR}" ]]; then
        preserve_converted_models
        if [[ "${CLEAN}" == "true" ]]; then
            log "REMOVING EXISTING WORKING COPY"
            rm -rf "${WORK_DIR}"
        else
            log "REUSING EXISTING WORKING COPY"
            info "${WORK_DIR}"
            info "Run with --clean after changing overlay/, patches/ or generators/."
            exit 0
        fi
    else
        mkdir -p "${OVMS_MODELS_DIR}"
    fi

    log "CREATING WORKING COPY"
    fetch_sources
    [[ -d "${WORK_DIR}" ]] || die "Working copy was not created: ${WORK_DIR}"
    snapshot_baseline

    log "CHECKING BASELINE DRIFT"
    check_baseline_drift

    log "APPLYING OVERLAY"
    apply_overlay

    log "APPLYING PATCHES"
    apply_patches

    log "APPLYING GENERATORS"
    apply_generators

    log "WORKING COPY READY"
    info "${WORK_DIR}"
    info "Model cache (persistent): ${OVMS_MODELS_DIR}"
    info "Inspect demo changes with: git -C ${WORK_DIR} diff HEAD"
}

main "$@"


