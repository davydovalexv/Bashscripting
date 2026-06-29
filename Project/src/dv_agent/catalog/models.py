from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from dv_agent.model.dv_schema import DvType


class ClassificationStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class DvRole(str, Enum):
    BUSINESS_KEY = "business_key"
    ATTRIBUTE = "attribute"
    GRAIN_KEY = "grain_key"
    LINK_KEY = "link_key"
    OPERATIONAL_KEY = "operational_key"


class ColumnProposal(BaseModel):
    table_schema: str = "public"
    table_name: str
    column_name: str
    data_type: str | None = None
    is_primary_key: bool = False
    references: str | None = None
    dv_type: DvType
    dv_target_entity: str
    dv_role: DvRole
    is_business_key: bool = False
    reasoning: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: ClassificationStatus = ClassificationStatus.PROPOSED

    @property
    def column_key(self) -> str:
        return f"{self.table_schema}.{self.table_name}.{self.column_name}"


class ClassificationCatalog(BaseModel):
    version: str = "1.0"
    source_path: str | None = None
    dialect: str | None = None
    model: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    proposals: list[ColumnProposal] = Field(default_factory=list)

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)

    def by_table(self, table_name: str) -> list[ColumnProposal]:
        return [p for p in self.proposals if p.table_name == table_name]

    def summary_counts(self) -> dict[str, int]:
        counts = {"hub": 0, "satellite": 0, "link": 0}
        for p in self.proposals:
            counts[p.dv_type.value] += 1
        return counts
