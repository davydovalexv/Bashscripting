from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DvType(str, Enum):
    HUB = "hub"
    SATELLITE = "satellite"
    LINK = "link"


class ColumnClassification(BaseModel):
    table_schema: str
    table_name: str
    column_name: str
    ordinal_position: int
    data_type: str
    is_nullable: str
    dv_type: DvType
    dv_target_entity: str
    dv_role: str
    is_business_key: bool
    description: str | None = None


class DvEntitySummary(BaseModel):
    dv_target_entity: str
    dv_type: DvType
    column_count: int
    source_columns: str


class SourceColumn(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    references: str | None = None


class SourceTable(BaseModel):
    name: str
    schema_name: str = "public"
    catalog_name: str | None = None
    columns: list[SourceColumn] = Field(default_factory=list)
    source_file: str | None = None
    dialect: str | None = None

    @property
    def qualified_name(self) -> str:
        parts = [p for p in (self.catalog_name, self.schema_name, self.name) if p]
        return ".".join(parts) if len(parts) > 1 else self.name
