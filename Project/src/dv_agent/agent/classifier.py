from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from dv_agent.agent.llm_client import LlmError, OllamaClient
from dv_agent.agent.prompts import build_table_prompt, get_system_prompt
from dv_agent.catalog.models import ClassificationCatalog, ColumnProposal, DvRole
from dv_agent.catalog.store import save_catalog
from dv_agent.config import AppConfig, load_config
from dv_agent.model.dv_schema import DvType, SourceTable


def _format_columns(table: SourceTable) -> str:
    lines: list[str] = []
    for col in table.columns:
        flags: list[str] = []
        if col.is_primary_key:
            flags.append("PK")
        if col.references:
            flags.append(f"FK->{col.references}")
        if not col.nullable:
            flags.append("NOT NULL")
        flag_text = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"  - {col.name}: {col.data_type}{flag_text}")
    return "\n".join(lines)


def _table_payload(table: SourceTable) -> dict:
    return {
        "name": table.name,
        "schema_name": table.schema_name,
        "columns_text": _format_columns(table),
    }


def _parse_column(
    table: SourceTable,
    raw: dict,
) -> ColumnProposal:
    col_name = raw["column_name"]
    source_col = next((c for c in table.columns if c.name == col_name), None)

    dv_type = DvType(raw["dv_type"])
    dv_role = DvRole(raw["dv_role"])

    return ColumnProposal(
        table_schema=table.schema_name,
        table_name=table.name,
        column_name=col_name,
        data_type=source_col.data_type if source_col else None,
        is_primary_key=source_col.is_primary_key if source_col else False,
        references=source_col.references if source_col else None,
        dv_type=dv_type,
        dv_target_entity=raw["dv_target_entity"],
        dv_role=dv_role,
        is_business_key=bool(raw.get("is_business_key", dv_role == DvRole.BUSINESS_KEY)),
        reasoning=raw.get("reasoning"),
        confidence=raw.get("confidence"),
    )


def propose_table(
    client: OllamaClient,
    table: SourceTable,
    *,
    retries: int = 2,
) -> list[ColumnProposal]:
    payload = _table_payload(table)
    user_prompt = build_table_prompt(payload)
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            result = client.chat_json(get_system_prompt(), user_prompt)
            columns = result.get("columns", [])
            if not columns:
                raise LlmError(f"Модель не вернула столбцы для {table.name}")

            proposals = [_parse_column(table, col) for col in columns]
            expected = {c.name for c in table.columns}
            got = {p.column_name for p in proposals}
            missing = expected - got
            if missing:
                raise LlmError(
                    f"Не хватает столбцов для {table.name}: {', '.join(sorted(missing))}"
                )
            return proposals
        except LlmError as exc:
            last_error = exc
            if "Таймаут" in str(exc) and attempt < retries:
                continue
            raise
        except (KeyError, ValueError) as exc:
            last_error = exc

    raise LlmError(str(last_error))


ProgressCallback = Callable[[int, int, str], None]
TableDoneCallback = Callable[[int, int, str, float], None]


def propose_classification(
    tables: list[SourceTable],
    config: AppConfig | None = None,
    *,
    source_path: str | None = None,
    dialect: str | None = None,
    checkpoint_path: Path | None = None,
    on_progress: ProgressCallback | None = None,
    on_table_done: TableDoneCallback | None = None,
    skip_warmup: bool = False,
) -> ClassificationCatalog:
    cfg = config or load_config()
    proposals: list[ColumnProposal] = []
    sorted_tables = sorted(tables, key=lambda t: t.qualified_name)

    with OllamaClient(cfg.llm) as client:
        if not client.ping():
            raise LlmError(
                f"Ollama недоступен ({cfg.llm.base_url}). "
                "Установите и запустите: ollama serve"
            )
        if not client.has_model():
            raise LlmError(
                f"Модель {cfg.llm.model} не найдена. "
                f"Выполните: ollama pull {cfg.llm.model}"
            )

        if not skip_warmup:
            client.warmup()

        for index, table in enumerate(sorted_tables, start=1):
            if on_progress:
                on_progress(index, len(sorted_tables), table.name)
            table_started = time.monotonic()
            proposals.extend(propose_table(client, table))
            if on_table_done:
                on_table_done(
                    index,
                    len(sorted_tables),
                    table.name,
                    time.monotonic() - table_started,
                )

            if checkpoint_path:
                partial = ClassificationCatalog(
                    source_path=source_path,
                    dialect=dialect,
                    model=cfg.llm.model,
                    proposals=list(proposals),
                )
                save_catalog(partial, checkpoint_path)

    return ClassificationCatalog(
        source_path=source_path,
        dialect=dialect,
        model=cfg.llm.model,
        proposals=proposals,
    )
