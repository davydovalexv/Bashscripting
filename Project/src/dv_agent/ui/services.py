from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from dv_agent.agent import LlmError, OllamaClient, propose_classification
from dv_agent.catalog.models import ClassificationCatalog
from dv_agent.catalog.store import default_proposed_path, save_catalog
from dv_agent.config import AppConfig, load_config
from dv_agent.parser.factory import parser_options_from_config
from dv_agent.parser.loader import parse_sql_path
from dv_agent.parser.options import ParseResult
from dv_agent.model.dv_schema import SourceTable

ProgressCallback = Callable[[int, int, str], None]


def uploads_dir(cfg: AppConfig | None = None) -> Path:
    config = cfg or load_config()
    path = config.resolve_path(config.paths.output) / "uploads" / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_workspace_files(cfg: AppConfig | None = None) -> list[Path]:
    directory = uploads_dir(cfg)
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in {".sql", ".ddl"}
    )


def save_uploaded_files(uploaded_files, cfg: AppConfig | None = None) -> list[Path]:
    directory = uploads_dir(cfg)
    saved: list[Path] = []
    for uploaded in uploaded_files:
        target = directory / uploaded.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(uploaded.getbuffer())
        saved.append(target)
    return saved


def clear_workspace(cfg: AppConfig | None = None) -> int:
    removed = 0
    for path in list_workspace_files(cfg):
        path.unlink()
        removed += 1
    return removed


def inspect_path(path: Path, cfg: AppConfig | None = None) -> ParseResult:
    config = cfg or load_config()
    return parse_sql_path(path, parser_options_from_config(config))


def parse_result_to_dataframe(parsed: ParseResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for table in sorted(parsed.tables, key=lambda item: item.qualified_name):
        pk = ", ".join(column.name for column in table.columns if column.is_primary_key) or "—"
        rows.append(
            {
                "schema": table.schema_name,
                "table": table.name,
                "columns": len(table.columns),
                "pk": pk,
                "file": Path(table.source_file).name if table.source_file else "—",
                "qualified": table.qualified_name,
            }
        )
    return pd.DataFrame(rows)


def issues_to_dataframe(parsed: ParseResult) -> pd.DataFrame:
    if not parsed.issues:
        return pd.DataFrame(columns=["level", "file", "message"])
    return pd.DataFrame(
        [
            {
                "level": issue.level,
                "file": Path(issue.file).name,
                "message": issue.message,
            }
            for issue in parsed.issues
        ]
    )



def llm_status(cfg: AppConfig | None = None) -> dict[str, str | bool]:
    config = cfg or load_config()
    try:
        with OllamaClient(config.llm) as client:
            if not client.ping():
                return {
                    "ok": False,
                    "message": f"Ollama недоступен ({config.llm.base_url})",
                    "model": config.llm.model,
                }
            if not client.has_model():
                return {
                    "ok": False,
                    "message": f"Модель не найдена. Выполните: ollama pull {config.llm.model}",
                    "model": config.llm.model,
                }
            return {"ok": True, "message": "Готов к классификации", "model": config.llm.model}
    except LlmError as exc:
        return {"ok": False, "message": str(exc), "model": config.llm.model}


def run_propose(
    tables: list[SourceTable],
    source_path: str,
    *,
    cfg: AppConfig | None = None,
    output_path: Path | None = None,
    timeout_sec: int | None = None,
    skip_warmup: bool = False,
    on_progress: ProgressCallback | None = None,
    on_table_done: Callable[[int, int, str, float], None] | None = None,
) -> ClassificationCatalog:
    config = cfg or load_config()
    if timeout_sec:
        config = config.model_copy(
            update={"llm": config.llm.model_copy(update={"timeout_sec": timeout_sec})}
        )

    out = output_path or default_proposed_path(config.resolve_path(config.paths.output))
    opts = parser_options_from_config(config)

    catalog = propose_classification(
        tables,
        config,
        source_path=source_path,
        dialect=opts.dialect_name,
        checkpoint_path=out,
        on_progress=on_progress,
        on_table_done=on_table_done,
        skip_warmup=skip_warmup,
    )
    save_catalog(catalog, out)
    return catalog


def list_example_paths(cfg: AppConfig | None = None) -> list[Path]:
    config = cfg or load_config()
    root = config.resolve_path(config.paths.sql_sources)
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".sql", ".ddl"}
    )
