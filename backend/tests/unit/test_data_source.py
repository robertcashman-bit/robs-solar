"""Unit tests for data_source helpers."""

from __future__ import annotations

from unittest.mock import patch

from app.db.models import MetricSampleRow
from app.services.data_source import (
    DATA_SOURCE_LIVE,
    DATA_SOURCE_SIMULATED,
    apply_sample_source_filter,
    current_data_source,
    filter_sample_rows,
    is_live_mode,
)


def test_current_data_source_simulator() -> None:
    with patch("app.services.data_source.settings") as mock_settings:
        mock_settings.adapter_mode = "simulator"
        assert current_data_source() == DATA_SOURCE_SIMULATED
        assert not is_live_mode()


def test_current_data_source_live() -> None:
    with patch("app.services.data_source.settings") as mock_settings:
        mock_settings.adapter_mode = "sunsynk_connect"
        assert current_data_source() == DATA_SOURCE_LIVE
        assert is_live_mode()


def test_filter_sample_rows_excludes_simulated_when_live() -> None:
    live_row = MetricSampleRow(data_source=DATA_SOURCE_LIVE)
    sim_row = MetricSampleRow(data_source=DATA_SOURCE_SIMULATED)
    with patch("app.services.data_source.is_live_mode", return_value=True):
        filtered = filter_sample_rows([live_row, sim_row])
    assert filtered == [live_row]


def test_apply_sample_source_filter_adds_where_clause_when_live() -> None:
    from sqlalchemy import select

    stmt = select(MetricSampleRow)
    with patch("app.services.data_source.is_live_mode", return_value=True):
        filtered = apply_sample_source_filter(stmt)
    assert "data_source" in str(filtered.whereclause)
