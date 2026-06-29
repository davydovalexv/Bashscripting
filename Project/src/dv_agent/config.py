from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "dv_user"
    password: str = "dv_pass"
    name: str = "source_db"
    source_schema: str = "src"
    meta_schema: str = "dv_meta"

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.name} "
            f"user={self.user} password={self.password}"
        )


class LlmConfig(BaseModel):
    provider: str = "ollama"
    model: str = "qwen2.5-coder:7b"
    base_url: str = "http://localhost:11434"
    timeout_sec: int = 120
    num_predict: int = 2048
    num_ctx: int = 8192
    keep_alive: str = "30m"


class PathsConfig(BaseModel):
    sql_sources: str = "../Files/Файлы к ML"
    output: str = "./output"


class ParserConfig(BaseModel):
    dialect: str = "postgres"
    default_schema: str = "public"
    recursive: bool = True
    patterns: list[str] = Field(default_factory=lambda: ["*.sql", "*.ddl"])


class AppConfig(BaseModel):
    paths: PathsConfig = Field(default_factory=PathsConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def resolve_path(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute():
            return path
        return (self.project_root / relative).resolve()


@lru_cache
def load_config(config_path: Path | None = None) -> AppConfig:
    root = Path(__file__).resolve().parents[2]
    env_path = os.getenv("DV_CONFIG_PATH")
    if config_path is None and env_path:
        config_path = Path(env_path)
    path = config_path or root / "config" / "default.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AppConfig.model_validate(data)
