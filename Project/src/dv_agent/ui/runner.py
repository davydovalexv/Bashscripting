"""Запуск Streamlit UI."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    try:
        from streamlit.web import cli as stcli
    except ImportError as exc:
        raise SystemExit(
            "Streamlit не установлен. Выполните: pip install -e '.[ui]'"
        ) from exc

    app_path = Path(__file__).resolve().parent / "streamlit_app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    sys.exit(stcli.main())
