#!/usr/bin/env bash

set -euo pipefail

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing required command: $1" >&2
        exit 1
    }
}

install_google_chrome() {
    if dpkg -s google-chrome-stable >/dev/null 2>&1; then
        echo "=== GOOGLE CHROME ALREADY INSTALLED ==="
        return
    fi

    echo "=== ADD CHROME REPOSITORY ==="
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | \
        sudo gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg

    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | \
        sudo tee /etc/apt/sources.list.d/google-chrome.list >/dev/null

    sudo apt-get update
    sudo apt-get install -y google-chrome-stable
}

install_docker_if_needed() {
    if command -v docker >/dev/null 2>&1; then
        echo "=== DOCKER ALREADY INSTALLED ==="
        return
    fi

    echo "=== INSTALL DOCKER ==="
    sudo install -m 0755 -d /etc/apt/keyrings

    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

main() {
    require_cmd curl
    require_cmd dpkg
    require_cmd gpg
    require_cmd sudo
    require_cmd tee

    echo "=== UPDATE SYSTEM ==="
    sudo apt-get update
    sudo apt-get upgrade -y

    echo "=== INSTALL BASE DEPENDENCIES ==="
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        git \
        yq \
        intel-gpu-tools \
        python3-poetry \
        python3-venv \
        python3-pip \
        tmux

    install_google_chrome
    install_docker_if_needed

    echo "=== CONFIGURE DOCKER ACCESS ==="
    sudo usermod -aG docker "$USER" || true

    if [[ -S /var/run/docker.sock ]]; then
        sudo chown root:docker /var/run/docker.sock
        sudo chmod 660 /var/run/docker.sock
    fi

    echo "=== DONE ==="
    echo "Run ./run_dlStreamer.sh to start the demo environment."
}

main "$@"
