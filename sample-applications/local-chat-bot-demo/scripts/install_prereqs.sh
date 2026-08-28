#!/usr/bin/env bash
# Host prerequisites for the Local Chat Bot demo (Ubuntu/Debian).
# Everything is installed conditionally, so re-running is cheap.

set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEMO_ROOT}/scripts/lib.sh"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TEMP_DIR}"' EXIT

install_gpg_keyring() {
    local url="$1"
    local output_path="$2"
    local temp_key_file="${TEMP_DIR}/$(basename "$output_path").asc"

    info "Fetching GPG key: ${url}"
    curl -fsSL --retry 5 --retry-delay 2 --retry-connrefused "$url" -o "$temp_key_file"

    if ! grep -q "BEGIN PGP PUBLIC KEY BLOCK" "$temp_key_file"; then
        echo "Downloaded data from ${url} is not a valid ASCII-armored OpenPGP key." >&2
        head -n 5 "$temp_key_file" >&2 || true
        return 1
    fi

    sudo gpg --dearmor --yes -o "$output_path" "$temp_key_file"
    sudo chmod 644 "$output_path"
}

# Must run before any repository is configured: install_gpg_keyring() needs curl
# and gpg, which the main package installation below would only provide later.
ensure_bootstrap_packages() {
    if command_exists curl && command_exists gpg; then
        log "BOOTSTRAP DEPENDENCIES ALREADY AVAILABLE: SKIPPING"
        return
    fi

    log "INSTALLING BOOTSTRAP DEPENDENCIES (ca-certificates, curl, gnupg)"
    sudo apt update
    sudo apt install -y ca-certificates curl gnupg
}

main() {
    local need_apt_update=false
    local need_chrome_install=false
    local need_docker_install=false
    local need_base_packages_install=false

    ensure_bootstrap_packages

    if command_exists google-chrome || command_exists google-chrome-stable; then
        log "GOOGLE CHROME ALREADY INSTALLED: SKIPPING"
    else
        need_chrome_install=true
        need_base_packages_install=true
        log "CONFIGURING GOOGLE CHROME REPOSITORY"
        sudo install -m 0755 -d /etc/apt/keyrings
        install_gpg_keyring "https://dl.google.com/linux/linux_signing_key.pub" "/etc/apt/keyrings/google-chrome.gpg"
        sudo tee /etc/apt/sources.list.d/google-chrome.list > /dev/null <<'EOF'
deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main
EOF
        need_apt_update=true
    fi

    if command_exists docker; then
        log "DOCKER ALREADY INSTALLED: SKIPPING"
    else
        need_docker_install=true
        need_base_packages_install=true
        log "CONFIGURING DOCKER REPOSITORY"
        sudo install -m 0755 -d /etc/apt/keyrings
        install_gpg_keyring "https://download.docker.com/linux/ubuntu/gpg" "/etc/apt/keyrings/docker.gpg"
        echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        need_apt_update=true
    fi


    if ! command_exists curl || ! command_exists gpg || ! command_exists git || \
       ! command_exists jq || ! command_exists python3 || ! command_exists pip3; then
        need_base_packages_install=true
    fi

    if [[ "$need_apt_update" == "true" ]]; then
        log "UPDATING PACKAGE INDEX"
        sudo apt update
    fi

    if [[ "$need_base_packages_install" == "true" ]]; then
        log "INSTALLING BASE DEPENDENCIES"
        sudo apt install -y ca-certificates curl gnupg git jq intel-gpu-tools python3-venv python3-pip
    else
        log "BASE DEPENDENCIES ALREADY AVAILABLE: SKIPPING"
    fi

    if [[ "$need_chrome_install" == "true" ]]; then
        log "INSTALLING GOOGLE CHROME"
        sudo apt install -y google-chrome-stable
    fi

    if [[ "$need_docker_install" == "true" ]]; then
        log "INSTALLING DOCKER"
        sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        sudo usermod -aG docker "$USER"
        sudo chown root:docker /var/run/docker.sock
        sudo chmod 660 /var/run/docker.sock
    fi


    log "PREREQUISITES READY"
}

main "$@"

