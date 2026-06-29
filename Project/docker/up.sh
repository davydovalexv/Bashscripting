#!/usr/bin/env bash
# Запуск стека: остановить host Ollama, поднять compose (модель тянется сервисом ollama-init)
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v systemctl >/dev/null 2>&1; then
  systemctl stop ollama 2>/dev/null || true
fi

docker compose up -d --build "$@"

echo ""
echo "Готово (модель загружается сервисом ollama-init при первом запуске)."
echo "  UI:         http://localhost:${DV_UI_PORT:-8501}"
echo "  PostgreSQL: localhost:${DV_POSTGRES_PORT:-5432}"
echo "  Ollama:     http://localhost:${DV_OLLAMA_PORT:-11434}"
