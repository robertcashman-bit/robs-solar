"""Live vs simulated data source helpers."""

from __future__ import annotations

from sqlalchemy import Select, true
from sqlalchemy.sql import ColumnElement

from app.config import settings
from app.db.models import MetricSampleRow

DATA_SOURCE_LIVE = "live"
DATA_SOURCE_SIMULATED = "simulated"


def current_data_source() -> str:
    return (
        DATA_SOURCE_SIMULATED
        if settings.adapter_mode.lower() == "simulator"
        else DATA_SOURCE_LIVE
    )


def is_live_mode() -> bool:
    return current_data_source() == DATA_SOURCE_LIVE


def sample_source_clause() -> ColumnElement[bool]:
    """When running live, exclude rows recorded under simulator mode."""
    if is_live_mode():
        return MetricSampleRow.data_source == DATA_SOURCE_LIVE
    return true()


def apply_sample_source_filter(stmt: Select) -> Select:
    return stmt.where(sample_source_clause())


def filter_sample_rows(rows: list[MetricSampleRow]) -> list[MetricSampleRow]:
    if not is_live_mode():
        return rows
    return [row for row in rows if row.data_source == DATA_SOURCE_LIVE]
