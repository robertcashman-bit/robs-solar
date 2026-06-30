import pytest
from pydantic import ValidationError

from app.schemas.domain import ExportLimitRequest


def test_export_limit_must_be_multiple_of_100() -> None:
    with pytest.raises(ValidationError):
        ExportLimitRequest(limit_w=2050)


def test_export_limit_valid() -> None:
    req = ExportLimitRequest(limit_w=2000)
    assert req.limit_w == 2000
