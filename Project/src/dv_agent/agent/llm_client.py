from __future__ import annotations

import json
import re
from typing import Any

import httpx

from dv_agent.config import LlmConfig


class LlmError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config: LlmConfig) -> None:
        self.config = config
        timeout = httpx.Timeout(
            connect=30.0,
            read=float(config.timeout_sec),
            write=30.0,
            pool=30.0,
        )
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def ping(self) -> bool:
        try:
            response = self._client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        response = self._client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]

    def has_model(self, model: str | None = None) -> bool:
        name = model or self.config.model
        models = self.list_models()
        return any(m == name or m.startswith(f"{name}:") for m in models)

    def warmup(self, model: str | None = None) -> None:
        """Загрузить модель в память коротким запросом (первый вызов самый долгий)."""
        self.chat_json(
            "Reply only with JSON.",
            '{"ok": true}',
            model=model,
        )

    def chat_json(self, system: str, user: str, model: str | None = None) -> dict[str, Any]:
        payload = {
            "model": model or self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
            "keep_alive": self.config.keep_alive,
            "options": {
                "num_predict": self.config.num_predict,
                "num_ctx": self.config.num_ctx,
            },
        }
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise LlmError(
                f"Ollama недоступен по адресу {self.config.base_url}. "
                "Запустите: ollama serve && ollama pull qwen2.5-coder:7b"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise LlmError(
                f"Таймаут Ollama ({self.config.timeout_sec} сек). "
                "Модель на CPU грузится долго — увеличьте: dv-agent propose --timeout 900"
            ) from exc
        except httpx.HTTPError as exc:
            raise LlmError(f"Ошибка Ollama API: {exc}") from exc

        content = response.json().get("message", {}).get("content", "")
        return _parse_json_content(content)


def _parse_json_content(content: str) -> dict[str, Any]:
    content = content.strip()
    if not content:
        raise LlmError("Пустой ответ модели")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LlmError(f"Не удалось разобрать JSON из ответа: {content[:200]}") from exc

    raise LlmError(f"Ответ не содержит JSON: {content[:200]}")
