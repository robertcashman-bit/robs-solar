import pytest

from app.services.forecast_service import forecast_service


@pytest.mark.asyncio
async def test_forecast_returns_days(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "daily": {
                    "time": ["2026-06-29", "2026-06-30"],
                    "shortwave_radiation_sum": [20.0, 18.0],
                }
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.forecast_service.httpx.AsyncClient",
        lambda **kw: FakeClient(),
    )
    result = await forecast_service.get_forecast(days=2)
    assert len(result["days"]) == 2
    assert result["days"][0]["predicted_kwh"] >= 0
