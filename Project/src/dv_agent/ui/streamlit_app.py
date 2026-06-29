from __future__ import annotations

import streamlit as st

from dv_agent.config import load_config
from dv_agent.ui.review_page import render_review_section
from dv_agent.ui.workflow_page import render_workflow_sections

UI_VERSION = "0.2"


def render_app() -> None:
    st.set_page_config(
        page_title="DV Agent",
        page_icon="🏛️",
        layout="wide",
    )

    cfg = load_config()
    output_dir = cfg.resolve_path(cfg.paths.output)

    st.title("DV Agent — Data Vault 2.0")
    st.caption(
        f"UI v{UI_VERSION} · один экран: загрузка SQL → inspect-sql → propose → прогресс → результаты"
    )

    with st.sidebar:
        st.markdown(f"**Версия UI:** {UI_VERSION}")
        st.caption(f"Ollama: {cfg.llm.base_url}")
        st.caption(f"Модель: {cfg.llm.model}")
        st.caption(f"Вывод: {output_dir}")

    render_workflow_sections(cfg, output_dir)
    st.divider()
    render_review_section(cfg, output_dir)


def main() -> None:
    render_app()


if __name__ == "__main__":
    render_app()
