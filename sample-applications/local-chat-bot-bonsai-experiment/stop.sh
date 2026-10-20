#!/usr/bin/env bash
set -euo pipefail

EXPERIMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WORK_ROOT="${EXPERIMENT_DIR}/.work"
export WORK_DIR="${WORK_ROOT}/chat-question-and-answer"
"${EXPERIMENT_DIR}/../local-chat-bot-demo/scripts/stop_local_chat_bot.sh" --remove-model-download
