from __future__ import annotations

import json
from pathlib import Path

from dv_agent.catalog.models import ClassificationCatalog


def default_proposed_path(output_dir: Path) -> Path:
    return output_dir / "classification_proposed.json"


def default_working_path(output_dir: Path) -> Path:
    return output_dir / "classification_working.json"


def save_catalog(catalog: ClassificationCatalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_catalog(path: Path) -> ClassificationCatalog:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ClassificationCatalog.model_validate(data)


def list_catalog_files(output_dir: Path) -> list[Path]:
    if not output_dir.is_dir():
        return []
    return sorted(output_dir.glob("classification*.json"))
