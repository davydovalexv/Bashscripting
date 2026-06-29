from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from dv_agent.config import load_config
from dv_agent.db.postgres import fetch_column_map, fetch_entity_summary, ping
from dv_agent.parser.factory import parser_options_from_config
from dv_agent.parser.loader import parse_sql_path
from dv_agent.parser.options import ParseOptions
from dv_agent.agent import LlmError, OllamaClient, propose_classification
from dv_agent.catalog import default_proposed_path, save_catalog
from dv_agent.catalog.models import (
    ClassificationCatalog,
    ClassificationStatus,
    ColumnProposal,
    DvRole,
)

app = typer.Typer(
    name="dv-agent",
    help="Локальный агент для анализа исходных данных и проектирования Data Vault 2.0",
)
console = Console()


@app.command()
def status() -> None:
    """Проверить конфигурацию и доступность PostgreSQL."""
    cfg = load_config()
    console.print(f"[bold]Project root:[/bold] {cfg.project_root}")
    console.print(f"[bold]SQL sources:[/bold] {cfg.resolve_path(cfg.paths.sql_sources)}")
    console.print(f"[bold]Database:[/bold] {cfg.database.host}:{cfg.database.port}/{cfg.database.name}")

    if ping(cfg):
        console.print("[green]PostgreSQL: OK[/green]")
    else:
        console.print("[red]PostgreSQL: недоступен[/red]")
        console.print("  Запустите: cd ../docker && docker compose up -d")


@app.command("inspect-sql")
def inspect_sql(
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Файл, каталог или glob (по умолчанию — paths.sql_sources из config)",
    ),
    dialect: str | None = typer.Option(
        None,
        "--dialect",
        "-d",
        help="SQL-диалект: postgres, mysql, tsql, oracle, sqlite, ...",
    ),
    recursive: bool | None = typer.Option(
        None,
        "--recursive/--no-recursive",
        help="Рекурсивный обход каталогов",
    ),
    export: Path | None = typer.Option(None, "--export", "-o", help="Сохранить результат в JSON"),
    show_warnings: bool = typer.Option(True, "--warnings/--no-warnings", help="Показать предупреждения"),
) -> None:
    """Разобрать DDL из произвольных SQL-файлов (файл / папка / glob)."""
    cfg = load_config()
    target = cfg.resolve_path(path or cfg.paths.sql_sources)

    opts = parser_options_from_config(cfg)
    if dialect:
        opts.dialect = dialect
    if recursive is not None:
        opts.recursive = recursive

    if not target.exists() and not any(c in str(target) for c in "*?[]"):
        raise typer.BadParameter(f"Путь не найден: {target}")

    parsed = parse_sql_path(target, opts)

    grid = Table(title=f"Таблицы из {target}")
    grid.add_column("Схема")
    grid.add_column("Таблица")
    grid.add_column("Колонок")
    grid.add_column("PK")
    grid.add_column("Файл")

    for t in sorted(parsed.tables, key=lambda x: x.qualified_name):
        pk = ", ".join(c.name for c in t.columns if c.is_primary_key) or "—"
        file_name = Path(t.source_file).name if t.source_file else "—"
        grid.add_row(t.schema_name, t.name, str(len(t.columns)), pk, file_name)

    console.print(grid)
    console.print(
        f"\nФайлов: {parsed.files_scanned} | с DDL: {parsed.files_with_ddl} | "
        f"таблиц: {parsed.table_count}"
    )

    if show_warnings and parsed.issues:
        console.print("\n[bold yellow]Предупреждения и ошибки:[/bold yellow]")
        for issue in parsed.issues:
            color = "red" if issue.level == "error" else "yellow"
            file_name = Path(issue.file).name
            console.print(f"  [{color}]{issue.level}[/{color}] {file_name}: {issue.message}")

    if export:
        export.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "path": str(target),
            "dialect": opts.dialect_name,
            "files_scanned": parsed.files_scanned,
            "tables": [t.model_dump() for t in parsed.tables],
            "issues": [issue.__dict__ for issue in parsed.issues],
        }
        export.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"\n[green]Сохранено:[/green] {export}")


@app.command("inspect-db")
def inspect_db(
    table: str | None = typer.Option(None, "--table", "-t", help="Фильтр по таблице"),
) -> None:
    """Показать разметку hub/satellite/link из PostgreSQL (dv_meta)."""
    if not ping():
        raise typer.Exit(code=1)

    rows = fetch_column_map(table_name=table)
    grid = Table(title="Разметка Data Vault 2.0")
    grid.add_column("Таблица")
    grid.add_column("Столбец")
    grid.add_column("DV тип")
    grid.add_column("Целевая сущность")
    grid.add_column("Роль")

    for row in rows:
        style = {"hub": "cyan", "satellite": "green", "link": "yellow"}[row.dv_type.value]
        grid.add_row(
            row.table_name,
            row.column_name,
            f"[{style}]{row.dv_type.value}[/{style}]",
            row.dv_target_entity,
            row.dv_role,
        )
    console.print(grid)


@app.command("summary")
def summary(
    export: Path | None = typer.Option(None, "--export", "-o", help="Сохранить JSON в файл"),
) -> None:
    """Сводка DV-сущностей из каталога dv_meta."""
    if not ping():
        raise typer.Exit(code=1)

    entities = fetch_entity_summary()
    grid = Table(title="DV-сущности")
    grid.add_column("Сущность")
    grid.add_column("Тип")
    grid.add_column("Столбцов")
    grid.add_column("Источник")

    for e in entities:
        grid.add_row(e.dv_target_entity, e.dv_type.value, str(e.column_count), e.source_columns)
    console.print(grid)

    if export:
        export.parent.mkdir(parents=True, exist_ok=True)
        payload = [e.model_dump(mode="json") for e in entities]
        export.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"\n[green]Сохранено:[/green] {export}")


@app.command("llm-status")
def llm_status() -> None:
    """Проверить доступность Ollama и модели Qwen."""
    cfg = load_config()
    console.print(f"[bold]Ollama:[/bold] {cfg.llm.base_url}")
    console.print(f"[bold]Модель:[/bold] {cfg.llm.model}")

    try:
        with OllamaClient(cfg.llm) as client:
            if not client.ping():
                console.print("[red]Ollama: недоступен[/red]")
                console.print("  Запустите: ollama serve")
                raise typer.Exit(code=1)

            models = client.list_models()
            console.print(f"[green]Ollama: OK[/green] ({len(models)} моделей)")
            if client.has_model():
                console.print(f"[green]Модель {cfg.llm.model}: найдена[/green]")
            else:
                console.print(f"[yellow]Модель {cfg.llm.model}: не найдена[/yellow]")
                console.print(f"  Выполните: ollama pull {cfg.llm.model}")
                raise typer.Exit(code=1)
    except LlmError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def propose(
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="SQL-файл или каталог для анализа",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Файл каталога (по умолчанию output/classification_proposed.json)",
    ),
    dialect: str | None = typer.Option(None, "--dialect", "-d"),
    table: str | None = typer.Option(
        None,
        "--table",
        "-t",
        help="Классифицировать только одну таблицу",
    ),
    timeout: int | None = typer.Option(
        None,
        "--timeout",
        help="Таймаут Ollama на одну таблицу, сек (по умолчанию из config, 600)",
    ),
    no_warmup: bool = typer.Option(
        False,
        "--no-warmup",
        help="Пропустить прогрев модели (не рекомендуется)",
    ),
) -> None:
    """Qwen предлагает разметку hub/satellite/link для SQL-схемы."""
    cfg = load_config()
    if timeout:
        cfg = cfg.model_copy(update={"llm": cfg.llm.model_copy(update={"timeout_sec": timeout})})
    target = cfg.resolve_path(path or cfg.paths.sql_sources)
    out_path = (
        cfg.resolve_path(output)
        if output
        else cfg.resolve_path(cfg.paths.output) / "classification_proposed.json"
    )

    opts = parser_options_from_config(cfg)
    if dialect:
        opts.dialect = dialect

    if not target.exists():
        raise typer.BadParameter(f"Путь не найден: {target}")

    console.print(f"[bold]Разбор SQL:[/bold] {target}")
    parsed = parse_sql_path(target, opts)
    if not parsed.tables:
        console.print("[red]Таблицы не найдены[/red]")
        raise typer.Exit(code=1)

    tables = parsed.tables
    if table:
        tables = [t for t in tables if t.name == table]
        if not tables:
            raise typer.BadParameter(f"Таблица не найдена: {table}")

    console.print(f"[bold]Таблиц для классификации:[/bold] {len(tables)}")
    console.print(f"[bold]Модель:[/bold] {cfg.llm.model}")
    console.print(f"[bold]Таймаут:[/bold] {cfg.llm.timeout_sec} сек / таблицу")
    console.print("[dim]Первый запуск: прогрев модели (1–5 мин на CPU)…[/dim]")

    def on_progress(current: int, total: int, name: str) -> None:
        console.print(f"  [cyan]({current}/{total})[/cyan] {name}…")

    try:
        catalog = propose_classification(
            tables,
            cfg,
            source_path=str(target),
            dialect=opts.dialect_name,
            checkpoint_path=out_path,
            on_progress=on_progress,
            skip_warmup=no_warmup,
        )
    except LlmError as exc:
        if out_path.is_file():
            console.print(
                f"[yellow]Частичный результат сохранён:[/yellow] {out_path} "
                "(откройте в dv-agent-ui)"
            )
        console.print(f"[red]Ошибка LLM:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    save_catalog(catalog, out_path)
    counts = catalog.summary_counts()
    console.print(f"\n[green]Сохранено:[/green] {out_path}")
    console.print(
        f"Столбцов: {catalog.proposal_count} | "
        f"hub: {counts['hub']} | satellite: {counts['satellite']} | link: {counts['link']}"
    )
    console.print("\nПросмотр и правка:")
    console.print("  dv-agent-ui")


@app.command("ui")
def launch_ui() -> None:
    """Запустить Streamlit UI для просмотра разметки."""
    from dv_agent.ui.runner import main as run_ui

    run_ui()


@app.command("export-meta")
def export_meta(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Путь к JSON (по умолчанию output/classification_proposed.json)",
    ),
) -> None:
    """Экспорт эталонной разметки из PostgreSQL (dv_meta) в JSON для UI."""
    if not ping():
        raise typer.Exit(code=1)

    cfg = load_config()
    out_path = (
        output.resolve()
        if output
        else cfg.resolve_path(cfg.paths.output) / "classification_proposed.json"
    )

    rows = fetch_column_map()
    proposals = [
        ColumnProposal(
            table_schema=row.table_schema,
            table_name=row.table_name,
            column_name=row.column_name,
            data_type=row.data_type,
            dv_type=row.dv_type,
            dv_target_entity=row.dv_target_entity,
            dv_role=DvRole(row.dv_role),
            is_business_key=row.is_business_key,
            reasoning=row.description,
            status=ClassificationStatus.PROPOSED,
        )
        for row in rows
    ]
    catalog = ClassificationCatalog(
        source_path="dv_meta (эталон)",
        model="manual",
        proposals=proposals,
    )
    save_catalog(catalog, out_path)
    console.print(f"[green]Экспортировано {len(proposals)} столбцов → {out_path}[/green]")
    console.print("Просмотр: dv-agent-ui")


if __name__ == "__main__":
    app()
