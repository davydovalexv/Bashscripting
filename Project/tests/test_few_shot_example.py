"""Проверка эталонного примера stg_crm_orders (без LLM)."""

import json
from pathlib import Path

import yaml

from dv_agent.agent.prompts import format_few_shot_for_prompt, get_system_prompt
from dv_agent.parser.loader import parse_sql_path
from dv_agent.parser.options import ParseOptions

FIXTURE = Path(__file__).parent / "fixtures" / "stg_crm_orders.sql"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "few_shot_examples.yaml"


def test_stg_crm_orders_parses():
    result = parse_sql_path(FIXTURE, ParseOptions(dialect="postgres"))
    assert result.table_count == 1
    assert result.tables[0].name == "stg_crm_orders"
    assert len(result.tables[0].columns) == 10


def test_few_shot_example_in_system_prompt():
    prompt = get_system_prompt()
    # CRM
    assert "stg_crm_orders" in prompt
    assert "hub_customer" in prompt
    assert "link_customer_order" in prompt
    # Oil (по сущностям и table_name в JSON)
    assert "hub_well" in prompt
    assert "sat_well_production" in prompt
    assert "link_well_production" in prompt
    assert "hub_delivery" in prompt
    assert '"table_name": "wells"' in prompt
    assert '"table_name": "production"' in prompt
    assert format_few_shot_for_prompt()


def test_oil_wells_golden_mapping():
    with CONFIG.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    example = next(ex for ex in data["examples"] if ex["id"] == "oil_wells")
    by_col = {c["column_name"]: c for c in example["columns"]}
    assert by_col["well_id"]["dv_type"] == "hub"
    assert by_col["well_id"]["dv_role"] == "business_key"
    assert by_col["name"]["dv_target_entity"] == "sat_well_details"


def test_oil_production_golden_mapping():
    with CONFIG.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    example = next(ex for ex in data["examples"] if ex["id"] == "oil_production")
    by_col = {c["column_name"]: c for c in example["columns"]}
    assert by_col["well_id"]["dv_type"] == "link"
    assert by_col["date"]["dv_role"] == "grain_key"


def test_golden_column_mapping():
    with CONFIG.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    example = next(ex for ex in data["examples"] if ex["id"] == "stg_crm_orders")
    by_col = {c["column_name"]: c for c in example["columns"]}

    assert by_col["customer_id"]["dv_type"] == "hub"
    assert by_col["customer_id"]["dv_target_entity"] == "hub_customer"
    assert by_col["order_num"]["dv_type"] == "hub"
    assert by_col["first_name"]["dv_target_entity"] == "sat_customer_profile"
    assert by_col["total_amount"]["dv_target_entity"] == "sat_order_details"

    entities = example["dv_entities"]
    assert "hub_customer" in entities["hubs"]
    assert "link_customer_order" in entities["links"]
    assert len(example["columns"]) == 10

    # JSON в промпте должен быть валидным
    payload = {"table_name": example["source_table"], "columns": example["columns"]}
    json.dumps(payload, ensure_ascii=False)
