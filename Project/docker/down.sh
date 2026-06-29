#!/usr/bin/env bash
# Остановка стека + остановка Ollama на хосте (освобождение порта 11434)
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose down "$@"

if command -v systemctl >/dev/null 2>&1; then
  systemctl stop ollama 2>/dev/null || true
fi
