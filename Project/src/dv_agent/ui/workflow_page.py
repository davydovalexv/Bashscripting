from __future__ import annotations

from pathlib import Path

import streamlit as st

from dv_agent.agent import LlmError
from dv_agent.catalog.store import default_proposed_path
from dv_agent.config import AppConfig
from dv_agent.ui.services import (
    clear_workspace,
    inspect_path,
    issues_to_dataframe,
    list_example_paths,
    list_workspace_files,
    llm_status,
    parse_result_to_dataframe,
    run_propose,
    save_uploaded_files,
    uploads_dir,
)
from dv_agent.ui.progress_tracker import ProgressTracker
from dv_agent.ui.review_page import render_results_summary


def _init_workflow_state() -> None:
    defaults = {
        "workflow_source_mode": "upload",
        "workflow_disk_path": "",
        "workflow_example_path": None,
        "workflow_parsed": None,
        "workflow_source_label": "",
        "workflow_log": [],
        "workflow_running": False,
        "catalog": None,
        "catalog_path": None,
        "dirty": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _resolve_source_path(cfg: AppConfig) -> Path | None:
    mode = st.session_state.workflow_source_mode
    if mode == "upload":
        files = list_workspace_files(cfg)
        return uploads_dir(cfg) if files else None
    if mode == "disk":
        raw = st.session_state.workflow_disk_path.strip()
        return Path(raw) if raw else None
    if mode == "example":
        selected = st.session_state.workflow_example_path
        return Path(selected) if selected else None
    return None


def _source_label(path: Path, mode: str) -> str:
    if mode == "upload":
        return str(uploads_dir())
    return str(path)


def render_workflow_sections(cfg: AppConfig, output_dir: Path) -> None:
    _init_workflow_state()

    status = llm_status(cfg)
    c1, c2, c3 = st.columns(3)
    c1.metric("Ollama", "OK" if status["ok"] else "ошибка")
    c2.metric("Модель", str(status.get("model", "—")))
    c3.metric("Таймаут", f"{cfg.llm.timeout_sec} сек / таблицу")
    if not status["ok"]:
        st.error(str(status["message"]))

    # --- Шаг 1: загрузка SQL ---
    st.subheader("1. Загрузка SQL")
    mode = st.radio(
        "Источник",
        options=["upload", "disk", "example"],
        format_func=lambda value: {
            "upload": "Загрузить файлы с компьютера",
            "disk": "Путь на диске (/data/sql/...)",
            "example": "Примеры из data/sql",
        }[value],
        horizontal=True,
        key="workflow_source_mode",
    )

    if mode == "upload":
        uploaded = st.file_uploader(
            "Перетащите SQL / DDL файлы",
            type=["sql", "ddl"],
            accept_multiple_files=True,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if uploaded and st.button("Сохранить файлы", type="primary", key="save_uploads"):
                saved = save_uploaded_files(uploaded, cfg)
                st.session_state.workflow_parsed = None
                st.success(f"Сохранено: {len(saved)} файл(ов) → {uploads_dir(cfg)}")
        with col_b:
            if list_workspace_files(cfg) and st.button("Очистить", key="clear_uploads"):
                count = clear_workspace(cfg)
                st.session_state.workflow_parsed = None
                st.info(f"Удалено: {count}")

        existing = list_workspace_files(cfg)
        if existing:
            st.markdown("**Файлы в рабочей папке:**")
            st.code("\n".join(file.name for file in existing), language="text")
        elif not uploaded:
            st.info("Загрузите один или несколько `.sql` / `.ddl` файлов.")

    elif mode == "disk":
        st.text_input(
            "Путь к файлу или каталогу",
            placeholder="/data/sql/oil",
            key="workflow_disk_path",
        )
    else:
        examples = list_example_paths(cfg)
        if examples:
            root = cfg.resolve_path(cfg.paths.sql_sources)
            labels = [str(path.relative_to(root)) for path in examples]
            choice = st.selectbox("Пример", labels, key="workflow_example_select")
            st.session_state.workflow_example_path = str(root / choice)
        else:
            st.warning(f"Примеры не найдены в {cfg.resolve_path(cfg.paths.sql_sources)}")

    # --- Шаг 2: inspect-sql ---
    st.subheader("2. Парсинг DDL (dv-agent inspect-sql)")
    source = _resolve_source_path(cfg)
    if source is None:
        st.info("Выберите или загрузите SQL выше.")
    else:
        st.text(f"Источник: {_source_label(source, st.session_state.workflow_source_mode)}")
        if st.button("Разобрать SQL", type="primary", key="parse_sql"):
            if not source.exists():
                st.error(f"Путь не найден: {source}")
            else:
                with st.spinner("Парсинг…"):
                    parsed = inspect_path(source, cfg)
                st.session_state.workflow_parsed = parsed
                st.session_state.workflow_source_label = _source_label(
                    source, st.session_state.workflow_source_mode
                )

    parsed = st.session_state.workflow_parsed
    if parsed is not None:
        st.markdown(
            f"**Файлов:** {parsed.files_scanned} · "
            f"**с DDL:** {parsed.files_with_ddl} · "
            f"**таблиц:** {parsed.table_count}"
        )
        table_df = parse_result_to_dataframe(parsed)
        if table_df.empty:
            st.warning("Таблицы не найдены (нужен CREATE TABLE).")
        else:
            st.dataframe(
                table_df.drop(columns=["qualified"]),
                use_container_width=True,
                hide_index=True,
            )
        issues_df = issues_to_dataframe(parsed)
        if not issues_df.empty:
            with st.expander("Предупреждения парсера", expanded=parsed.has_errors):
                st.dataframe(issues_df, use_container_width=True, hide_index=True)

    # --- Шаг 3: propose ---
    st.subheader("3. Классификация (dv-agent propose)")
    if parsed is None or not parsed.tables:
        st.info("Сначала разберите SQL (шаг 2).")
        return

    table_names = sorted({table.name for table in parsed.tables})
    selected_tables = st.multiselect(
        "Таблицы",
        options=table_names,
        default=table_names,
        key="propose_tables",
    )
    col1, col2 = st.columns(2)
    timeout = col1.number_input(
        "Таймаут на таблицу (сек)",
        min_value=120,
        max_value=3600,
        value=cfg.llm.timeout_sec,
        step=60,
        key="propose_timeout",
    )
    skip_warmup = col2.checkbox(
        "Пропустить прогрев модели",
        value=False,
        key="propose_skip_warmup",
        help="Не делать отдельный короткий запрос перед классификацией. "
        "Первая таблица всё равно может занять 2–5 мин на CPU (загрузка модели в память).",
    )

    # --- Шаг 4: прогресс ---
    st.subheader("4. Прогресс обработки")
    progress_bar = st.progress(
        st.session_state.get("workflow_progress", 0.0),
        text=st.session_state.get("workflow_progress_text", "Ожидание запуска…"),
    )
    status_box = st.empty()
    eta_box = st.empty()
    if st.session_state.workflow_log:
        st.code("\n".join(st.session_state.workflow_log), language="text")

    if not status["ok"]:
        st.warning("Ollama недоступен — классификация невозможна.")
        return
    if not selected_tables:
        st.warning("Выберите хотя бы одну таблицу.")
        return

    out_path = default_proposed_path(output_dir)
    if st.button(
        "Запустить классификацию",
        type="primary",
        key="run_propose",
        disabled=st.session_state.workflow_running,
    ):
        st.session_state.workflow_running = True
        st.session_state.workflow_log = []
        tables = [table for table in parsed.tables if table.name in selected_tables]
        tracker = ProgressTracker(total=len(tables))

        def on_progress(current: int, total: int, name: str) -> None:
            tracker.on_table_start(current, name)
            line = tracker.status_line(current, total, name, phase="start")
            fraction = tracker.progress_fraction(current, done=False)
            st.session_state.workflow_progress = max(fraction, 0.02)
            st.session_state.workflow_progress_text = line
            st.session_state.workflow_log.append(line)
            progress_bar.progress(st.session_state.workflow_progress, text=line)
            status_box.info(f"⏳ {line}")
            eta_box.caption(
                "Оценка уточняется после каждой таблицы"
                if not tracker.table_durations
                else f"Среднее на таблицу: {tracker.avg_table_seconds():.0f} сек"
            )

        def on_table_done(current: int, total: int, name: str, elapsed_sec: float) -> None:
            tracker.on_table_done(current, name, elapsed_sec)
            line = tracker.status_line(current, total, name, phase="done")
            fraction = tracker.progress_fraction(current, done=True)
            st.session_state.workflow_progress = fraction
            st.session_state.workflow_progress_text = line
            st.session_state.workflow_log.append(f"✓ {line}")
            progress_bar.progress(fraction, text=line)
            status_box.success(f"✓ {line}")
            if current < total:
                eta_box.caption(
                    f"Среднее на таблицу: {elapsed_sec:.0f} сек · "
                    f"до конца ~{tracker.remaining_seconds(current + 1):.0f} сек"
                )
            else:
                eta_box.empty()

        skip_warmup_now = bool(st.session_state.get("propose_skip_warmup", skip_warmup))
        spinner_text = (
            "Классификация…"
            if skip_warmup_now
            else "Прогрев модели и классификация… (первый запуск на CPU долгий)"
        )

        try:
            with st.spinner(spinner_text):
                catalog = run_propose(
                    tables,
                    st.session_state.workflow_source_label,
                    cfg=cfg,
                    output_path=out_path,
                    timeout_sec=int(timeout),
                    skip_warmup=skip_warmup_now,
                    on_progress=on_progress,
                    on_table_done=on_table_done,
                )
        except LlmError as exc:
            st.session_state.workflow_running = False
            progress_bar.progress(0, text="Ошибка")
            status_box.error(str(exc))
            if out_path.is_file():
                st.warning(f"Частичный результат: {out_path.name}")
            return

        st.session_state.workflow_running = False
        st.session_state.workflow_progress = 1.0
        st.session_state.workflow_progress_text = "Готово"
        st.session_state.catalog = catalog
        st.session_state.catalog_path = out_path
        st.session_state.dirty = False
        progress_bar.progress(1.0, text="Готово")
        status_box.success(f"Сохранено {catalog.proposal_count} столбцов → {out_path.name}")

    # --- Шаг 5: итоги (краткая сводка) ---
    st.subheader("5. Итоги")
    catalog = st.session_state.get("catalog")
    if catalog is None and out_path.is_file():
        from dv_agent.catalog.store import load_catalog

        catalog = load_catalog(out_path)
        st.session_state.catalog = catalog
        st.session_state.catalog_path = out_path

    if catalog is None:
        st.info("После классификации здесь появится сводка. Ниже — таблица для правки.")
    else:
        render_results_summary(catalog)
        st.caption(f"Файл: {st.session_state.catalog_path}")
