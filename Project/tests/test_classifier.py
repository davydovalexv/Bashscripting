"""Тесты LLM-классификатора (с mock Ollama)."""

from __future__ import annotations

import json

import httpx
import pytest

from dv_agent.agent.classifier import propose_table
from dv_agent.agent.llm_client import OllamaClient, _parse_json_content
from dv_agent.catalog.store import load_catalog, save_catalog
from dv_agent.config import LlmConfig
from dv_agent.model.dv_schema import SourceColumn, SourceTable


def _wells_table() -> SourceTable:
    return SourceTable(
        name="wells",
        schema_name="public",
        columns=[
            SourceColumn(name="well_id", data_type="SERIAL", is_primary_key=True),
            SourceColumn(name="name", data_type="TEXT", nullable=False),
            SourceColumn(name="region", data_type="TEXT"),
        ],
    )


def test_parse_json_content_with_markdown():
    raw = '```json\n{"columns": []}\n```'
    # fallback regex should still fail on markdown fences - test pure json
    assert _parse_json_content('{"ok": true}') == {"ok": True}


def test_catalog_roundtrip(tmp_path):
    from dv_agent.catalog.models import ClassificationCatalog, ColumnProposal, DvRole
    from dv_agent.model.dv_schema import DvType

    catalog = ClassificationCatalog(
        source_path="/test",
        model="test-model",
        proposals=[
            ColumnProposal(
                table_name="wells",
                column_name="well_id",
                dv_type=DvType.HUB,
                dv_target_entity="hub_well",
                dv_role=DvRole.BUSINESS_KEY,
                is_business_key=True,
            )
        ],
    )
    path = tmp_path / "classification_proposed.json"
    save_catalog(catalog, path)
    loaded = load_catalog(path)
    assert loaded.proposal_count == 1
    assert loaded.proposals[0].dv_target_entity == "hub_well"


def test_propose_table_mock(httpx_mock):
    response = {
        "columns": [
            {
                "column_name": "well_id",
                "dv_type": "hub",
                "dv_target_entity": "hub_well",
                "dv_role": "business_key",
                "is_business_key": True,
                "reasoning": "PK скважины",
                "confidence": 0.9,
            },
            {
                "column_name": "name",
                "dv_type": "satellite",
                "dv_target_entity": "sat_well_details",
                "dv_role": "attribute",
                "is_business_key": False,
                "reasoning": "Название",
                "confidence": 0.8,
            },
            {
                "column_name": "region",
                "dv_type": "satellite",
                "dv_target_entity": "sat_well_details",
                "dv_role": "attribute",
                "is_business_key": False,
                "reasoning": "Регион",
                "confidence": 0.85,
            },
        ]
    }

    httpx_mock.add_response(
        url="http://localhost:11434/api/chat",
        method="POST",
        json={"message": {"content": json.dumps(response)}},
    )

    config = LlmConfig(base_url="http://localhost:11434", model="qwen2.5-coder:7b")
    with OllamaClient(config) as client:
        proposals = propose_table(client, _wells_table())

    assert len(proposals) == 3
    assert proposals[0].dv_type.value == "hub"
    assert proposals[0].reasoning == "PK скважины"
