from __future__ import annotations

from dv_agent.config import AppConfig, load_config
from dv_agent.parser.options import ParseOptions, SqlDialect


def parser_options_from_config(config: AppConfig | None = None) -> ParseOptions:
    cfg = config or load_config()
    p = cfg.parser
    return ParseOptions(
        dialect=SqlDialect(p.dialect),
        default_schema=p.default_schema,
        recursive=p.recursive,
        patterns=tuple(p.patterns),
    )
