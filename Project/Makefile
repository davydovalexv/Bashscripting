.PHONY: up down logs

# Полный цикл: остановка host Ollama + docker compose
up:
	systemctl stop ollama 2>/dev/null || true
	docker compose up -d --build

down:
	docker compose down
	systemctl stop ollama 2>/dev/null || true

logs:
	docker compose logs -f ui ollama ollama-init
