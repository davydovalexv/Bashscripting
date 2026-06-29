from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


@lru_cache
def load_few_shot_examples() -> list[dict]:
    path = _CONFIG_DIR / "few_shot_examples.yaml"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("examples", [])


def format_few_shot_for_prompt() -> str:
    """Текст эталонных примеров для system prompt."""
    examples = load_few_shot_examples()
    if not examples:
        return ""

    blocks: list[str] = ["\n## Эталонные примеры разметки\n"]
    for ex in examples:
        blocks.append(f"### Пример [{ex.get('id')}]: {ex.get('title', ex.get('id'))}")
        if ex.get("description"):
            blocks.append(str(ex["description"]).strip())
        if ex.get("rules"):
            blocks.append("Правила:")
            for rule in ex["rules"]:
                blocks.append(f"- {rule}")
        if ex.get("dv_entities"):
            blocks.append(f"DV-сущности: {json.dumps(ex['dv_entities'], ensure_ascii=False)}")
        if ex.get("columns"):
            blocks.append("Разметка столбцов (JSON):")
            payload = {
                "table_name": ex.get("source_table", "unknown"),
                "columns": ex["columns"],
            }
            blocks.append(json.dumps(payload, ensure_ascii=False, indent=2))
        blocks.append("")
    return "\n".join(blocks)


SYSTEM_PROMPT_BASE = """\
Ты — эксперт по Data Vault 2.0. Твоя задача — классифицировать столбцы исходных таблиц.

Типы DV (dv_type):
- hub — бизнес-ключ стабильной сущности (клиент, заказ, скважина)
- satellite — описательный атрибут, метрика или техническое поле загрузки
- link — столбец, связывающий два хаба (FK, пара BK в плоской staging-таблице)

Роли (dv_role):
- business_key — BK хаба
- attribute — описательное поле сателлита
- grain_key — ключ зернистости (date, timestamp)
- link_key — ключ связи между хабами (FK или второй BK в связке)
- operational_key — суррогатный PK источника или load_date / record_source

Правила для плоских staging-таблиц (несколько сущностей в одной строке):
1. Каждый устойчивый ID (customer_id, order_num) → hub с business_key.
2. Атрибуты группируются по сущности → satellite (sat_customer_profile, sat_order_details).
3. Связь M:N или транзакция между хабами → link (link_customer_order из customer_id + order_num).
   Столбцы-BK при этом остаются hub; линк выводится из комбинации ключей.
4. load_date и record_source → operational_key (технические поля DV).

Правила именования:
- hub: hub_<entity>
- satellite: sat_<entity>_profile / sat_<entity>_details
- link: link_<entity1>_<entity2>

Отвечай ТОЛЬКО валидным JSON без markdown.
"""


def get_system_prompt() -> str:
    return SYSTEM_PROMPT_BASE + format_few_shot_for_prompt()


def build_table_prompt(table: dict) -> str:
    return f"""\
Классифицируй КАЖДЫЙ столбец таблицы для Raw Vault 2.0.
- Плоская staging (клиент+заказ в строке) → пример stg_crm_orders
- Справочник / факт / логистика → примеры oil_wells, oil_production, oil_deliveries

Таблица: {table['schema_name']}.{table['name']}
Столбцы:
{table['columns_text']}

Верни JSON:
{{
  "table_name": "{table['name']}",
  "columns": [
    {{
      "column_name": "...",
      "dv_type": "hub|satellite|link",
      "dv_target_entity": "hub_...|sat_...|link_...",
      "dv_role": "business_key|attribute|grain_key|link_key|operational_key",
      "is_business_key": false,
      "reasoning": "краткое обоснование на русском",
      "confidence": 0.85
    }}
  ]
}}
"""
