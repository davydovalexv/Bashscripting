from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from dv_agent.catalog.models import ClassificationCatalog, ClassificationStatus, ColumnProposal, DvRole
from dv_agent.catalog.store import (
    default_proposed_path,
    default_working_path,
    list_catalog_files,
    load_catalog,
    save_catalog,
)
from dv_agent.config import AppConfig
from dv_agent.model.dv_schema import DvType

DV_TYPE_OPTIONS = [item.value for item in DvType]
DV_ROLE_OPTIONS = [item.value for item in DvRole]
STATUS_OPTIONS = [item.value for item in ClassificationStatus]


def _catalog_to_df(catalog: ClassificationCatalog) -> pd.DataFrame:
    rows = [proposal.model_dump(mode="json") for proposal in catalog.proposals]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for column in ("dv_type", "dv_role", "status"):
        if column in df.columns:
            df[column] = df[column].astype(str)
    return df


def _df_to_catalog(df: pd.DataFrame, meta: ClassificationCatalog) -> ClassificationCatalog:
    proposals: list[ColumnProposal] = []
    for record in df.to_dict(orient="records"):
        record["dv_type"] = DvType(record["dv_type"])
        record["dv_role"] = DvRole(record["dv_role"])
        record["status"] = ClassificationStatus(record["status"])
        proposals.append(ColumnProposal.model_validate(record))
    return meta.model_copy(update={"proposals": proposals})


def render_results_summary(catalog: ClassificationCatalog) -> None:
    counts = catalog.summary_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Столбцов", catalog.proposal_count)
    c2.metric("Hub", counts["hub"])
    c3.metric("Satellite", counts["satellite"])
    c4.metric("Link", counts["link"])


def _load_catalog_if_needed(output_dir: Path) -> None:
    if st.session_state.get("catalog") is not None:
        return
    proposed = default_proposed_path(output_dir)
    if proposed.is_file():
        st.session_state.catalog = load_catalog(proposed)
        st.session_state.catalog_path = proposed


def render_review_section(cfg: AppConfig, output_dir: Path) -> None:
    st.subheader("Правка разметки")
    st.caption("Фильтры, изменение dv_type / роли / статуса, сохранение.")

    st.session_state.setdefault("catalog", None)
    st.session_state.setdefault("catalog_path", None)
    st.session_state.setdefault("dirty", False)

    files = list_catalog_files(output_dir)
    if not files:
        files = [default_proposed_path(output_dir)]
    labels = [path.name for path in files]
    proposed = default_proposed_path(output_dir)
    default_idx = files.index(proposed) if proposed in files else 0

    col_load, col_file = st.columns([1, 3])
    with col_file:
        selected_label = st.selectbox("Файл каталога", labels, index=default_idx)
    selected_path = next(path for path in files if path.name == selected_label)
    with col_load:
        if st.button("Загрузить файл", use_container_width=True):
            if selected_path.is_file():
                st.session_state.catalog = load_catalog(selected_path)
                st.session_state.catalog_path = selected_path
                st.session_state.dirty = False
                st.rerun()
            else:
                st.error(f"Файл не найден: {selected_path}")

    _load_catalog_if_needed(output_dir)
    if st.session_state.catalog is None:
        st.warning("Нет результатов. Выполните шаги 1–4 выше.")
        return

    catalog: ClassificationCatalog = st.session_state.catalog
    df = _catalog_to_df(catalog)
    if df.empty:
        st.warning("Каталог пуст.")
        return

    tab1, tab2, tab3 = st.tabs(["Таблица", "По таблицам", "Сводка DV-сущностей"])

    with tab1:
        f1, f2, f3 = st.columns(3)
        table_filter = f1.selectbox("Таблица", ["Все"] + sorted(df["table_name"].unique()))
        type_filter = f2.selectbox("DV тип", ["Все"] + DV_TYPE_OPTIONS)
        status_filter = f3.selectbox("Статус", ["Все"] + STATUS_OPTIONS)

        view = df.copy()
        if table_filter != "Все":
            view = view[view["table_name"] == table_filter]
        if type_filter != "Все":
            view = view[view["dv_type"] == type_filter]
        if status_filter != "Все":
            view = view[view["status"] == status_filter]

        edited = st.data_editor(
            view,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "dv_type": st.column_config.SelectboxColumn("DV тип", options=DV_TYPE_OPTIONS),
                "dv_role": st.column_config.SelectboxColumn("Роль", options=DV_ROLE_OPTIONS),
                "status": st.column_config.SelectboxColumn("Статус", options=STATUS_OPTIONS),
                "reasoning": st.column_config.TextColumn("Обоснование", width="large"),
                "confidence": st.column_config.NumberColumn("Уверенность", min_value=0, max_value=1),
                "is_business_key": st.column_config.CheckboxColumn("BK"),
            },
            disabled=[
                "table_schema",
                "table_name",
                "column_name",
                "data_type",
                "is_primary_key",
                "references",
            ],
            key="editor_main",
        )

        col_save, col_working, _ = st.columns([1, 1, 2])
        with col_save:
            if st.button("Сохранить", type="primary"):
                merged = df.copy()
                edited_index = edited.set_index(["table_schema", "table_name", "column_name"])
                merged_index = merged.set_index(["table_schema", "table_name", "column_name"])
                merged_index.update(edited_index)
                updated = _df_to_catalog(merged_index.reset_index(), catalog)
                path = st.session_state.catalog_path or default_proposed_path(output_dir)
                save_catalog(updated, path)
                st.session_state.catalog = updated
                st.session_state.dirty = False
                st.success(f"Сохранено: {path}")

        with col_working:
            if st.button("Сохранить рабочую копию"):
                merged = df.copy()
                edited_index = edited.set_index(["table_schema", "table_name", "column_name"])
                merged_index = merged.set_index(["table_schema", "table_name", "column_name"])
                merged_index.update(edited_index)
                updated = _df_to_catalog(merged_index.reset_index(), catalog)
                working = default_working_path(output_dir)
                save_catalog(updated, working)
                st.session_state.catalog = updated
                st.session_state.catalog_path = working
                st.success(f"Рабочая копия: {working}")

    with tab2:
        for table_name in sorted(df["table_name"].unique()):
            part = df[df["table_name"] == table_name]
            with st.expander(f"{table_name} ({len(part)} столбцов)", expanded=False):
                st.dataframe(
                    part[
                        [
                            "column_name",
                            "data_type",
                            "dv_type",
                            "dv_target_entity",
                            "dv_role",
                            "reasoning",
                            "status",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

    with tab3:
        summary = (
            df.groupby(["dv_target_entity", "dv_type"])
            .agg(
                columns=("column_name", lambda values: ", ".join(values)),
                count=("column_name", "count"),
            )
            .reset_index()
            .sort_values(["dv_type", "dv_target_entity"])
        )
        st.dataframe(summary, use_container_width=True, hide_index=True)


# Совместимость со старым импортом
def render_review_page(cfg: AppConfig, output_dir: Path) -> None:
    render_review_section(cfg, output_dir)
