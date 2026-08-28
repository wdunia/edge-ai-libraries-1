#!/usr/bin/env bash
# Regenerate patches/, overlay/ and overlay/MANIFEST.sha256 from the working copy.
#
# Typical workflow when the demo needs a change:
#   1. ./scripts/prepare_workspace.sh
#   2. edit files in .work/chat-question-and-answer
#   3. ./scripts/make_patches.sh [--refresh-overlay] [--refresh-manifest]
#
# The working copy is a throwaway git repository whose single commit is the
# pristine sample application, so `git diff` there is exactly the demo delta.

set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEMO_ROOT}/scripts/lib.sh"

REFRESH_OVERLAY=false
REFRESH_MANIFEST=false

usage() {
    cat <<'EOF'
Usage: ./scripts/make_patches.sh [--refresh-overlay] [--refresh-manifest]

  --refresh-overlay    Copy the current working-copy version of every overlay
                       file back into overlay/.
  --refresh-manifest   Re-fingerprint the baseline for overlay drift detection.
  --help               Show this message.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --refresh-overlay) REFRESH_OVERLAY=true ;;
        --refresh-manifest) REFRESH_MANIFEST=true ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
    shift
done

require_cmd git
require_cmd python3
require_workspace
[[ -d "${WORK_DIR}/.git" ]] || die "Working copy is not a git repository. Recreate it with scripts/prepare_workspace.sh --clean"

# patch file name -> space separated list of files (relative to the app root)
PATCH_MAP=(
    "010-app-server.patch|app/server.py"
    "020-app-chain.patch|app/chain.py"
    "030-pyproject-psutil.patch|pyproject.toml"
    "040-ui-conversation.patch|ui/react/src/components/Conversation/Conversation.tsx ui/react/src/components/Conversation/ConversationSideBar.tsx"
    "050-ui-redux.patch|ui/react/src/redux/Conversation/Conversation.ts ui/react/src/redux/Conversation/ConversationSlice.ts"
)

# Files owned by generators - expected to differ, never captured as patches.
GENERATED_FILES=(
    "setup.sh"
    "Dockerfile"
    "ui/react/Dockerfile"
    "ui/react/.env"
    "ui/react/src/config.ts"
    "ui/react/package.json"
)

log "REGENERATING PATCHES"
declare -a patched_files=()
for entry in "${PATCH_MAP[@]}"; do
    name="${entry%%|*}"
    files="${entry#*|}"
    # `git apply --3way` stages its result, so always diff against the baseline commit.
    # shellcheck disable=SC2086
    git -C "${WORK_DIR}" diff HEAD -- ${files} > "${DEMO_ROOT}/patches/${name}"
    if [[ ! -s "${DEMO_ROOT}/patches/${name}" ]]; then
        warn "${name} is empty (no changes in: ${files})"
    else
        info "${name}"
    fi
    # shellcheck disable=SC2206
    patched_files+=(${files})
done

if [[ "${REFRESH_OVERLAY}" == "true" ]]; then
    log "REFRESHING OVERLAY FILES"
    while IFS= read -r rel; do
        [[ -f "${WORK_DIR}/${rel}" ]] || { warn "missing in working copy: ${rel}"; continue; }
        mkdir -p "$(dirname "${DEMO_ROOT}/overlay/${rel}")"
        cp "${WORK_DIR}/${rel}" "${DEMO_ROOT}/overlay/${rel}"
        info "${rel}"
    done < <(cd "${DEMO_ROOT}/overlay" && find . -type f ! -name MANIFEST.sha256 -printf '%P\n')
fi

if [[ "${REFRESH_MANIFEST}" == "true" ]]; then
    log "REFRESHING BASELINE MANIFEST"
    pristine_dir="$(mktemp -d)"
    trap 'rm -rf "${pristine_dir}"' EXIT
    git -C "${WORK_DIR}" archive --format=tar HEAD | tar -x -C "${pristine_dir}"
    python3 "${DEMO_ROOT}/generators/manifest.py" write \
        --overlay "${DEMO_ROOT}/overlay" \
        --root "${pristine_dir}" \
        --out "${DEMO_ROOT}/overlay/MANIFEST.sha256"
fi

log "SANITY CHECK: UNCLASSIFIED CHANGES"
mapfile -t changed < <(git -C "${WORK_DIR}" diff HEAD --name-only; git -C "${WORK_DIR}" ls-files --others --exclude-standard)
unclassified=()
for file in "${changed[@]}"; do
    [[ -z "${file}" ]] && continue
    known=false
    for known_file in "${patched_files[@]}" "${GENERATED_FILES[@]}"; do
        [[ "${file}" == "${known_file}" ]] && { known=true; break; }
    done
    [[ "${known}" == "true" ]] && continue
    [[ -f "${DEMO_ROOT}/overlay/${file}" ]] && continue
    unclassified+=("${file}")
done

if (( ${#unclassified[@]} > 0 )); then
    warn "changes not covered by patches/, overlay/ or generators:"
    printf '  - %s\n' "${unclassified[@]}" >&2
    warn "add them to PATCH_MAP, to overlay/, or revert them in the working copy."
else
    info "All working-copy changes are covered."
fi

log "DONE"



