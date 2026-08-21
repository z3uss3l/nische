from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class TrendRecord(BaseModel):
    """Kanonischer Datenvertrag. Quellenspezifische Felder bleiben erhalten."""
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    title: str = ""
    url: str = ""
    date: str = ""
    score: float | None = None


@dataclass
class SourceResult:
    source: str
    status: str = "ok"  # ok, disabled, empty, error
    records: list[dict[str, Any]] | None = None
    error: str | None = None
    fetched_at: str | None = None
    latency_ms: int | None = None
    cached: bool = False
    total_available: int | None = None
    valid_records: int | None = None
    invalid_records: int = 0

    def __post_init__(self):
        if self.records is None:
            self.records = []
        if self.fetched_at is None:
            self.fetched_at = datetime.now(timezone.utc).isoformat()
        if self.valid_records is None:
            self.valid_records = len(self.records)

    @property
    def count(self) -> int:
        return len(self.records or [])

    def to_dict(self):
        return asdict(self)


def validate_records(records: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], int]:
    valid: list[dict[str, Any]] = []
    invalid = 0
    for raw in records or []:
        try:
            item = TrendRecord.model_validate(raw)
            valid.append(item.model_dump())
        except ValidationError:
            invalid += 1
    return valid, invalid
