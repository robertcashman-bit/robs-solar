import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_viewer, validate_csrf
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import (
    AuditOutcome,
    OctopusConfig,
    OctopusConfigStatus,
    OctopusDiscoverRequest,
    OctopusDiscoverResult,
    OctopusMeterPower,
    OctopusRatePlan,
)
from app.services.audit_service import audit_service
from app.services.octopus_client import octopus_client
from app.services.octopus_settings_service import octopus_settings_service

router = APIRouter(prefix="/octopus", tags=["octopus"])


def _agile_price_payload(rates: list[dict]) -> dict:
    current = rates[0] if rates else None
    sorted_rates = sorted(rates, key=lambda r: r["value_inc_vat"])
    cheapest = sorted_rates[:6]
    expensive = sorted_rates[-3:] if len(sorted_rates) >= 3 else []
    plunge = any(r["value_inc_vat"] < 0 for r in rates)
    return {
        "current": current,
        "rates": rates,
        "cheapest_slots": cheapest,
        "expensive_slots": expensive,
        "plunge_pricing": plunge,
    }


@router.get("/tariff")
async def octopus_tariff(_: SessionData = Depends(require_viewer)) -> dict:
    if not octopus_client.configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Octopus API key not configured",
        )
    info = await octopus_client.get_tariff_info()
    return info.__dict__


@router.get("/prices")
async def octopus_prices(_: SessionData = Depends(require_viewer)) -> dict:
    if not octopus_client.configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Octopus API key not configured",
        )
    tariff = await octopus_client.get_tariff_info()
    agile_rates = await octopus_client.get_agile_rates()
    agile = _agile_price_payload(agile_rates)
    return {
        "tariff": tariff.__dict__,
        "agile": agile,
        # Back-compat for scheduler overlay (Agile half-hourly slots).
        **agile,
    }


@router.get("/rate-plan", response_model=OctopusRatePlan)
async def octopus_rate_plan(_: SessionData = Depends(require_viewer)) -> OctopusRatePlan:
    if not octopus_client.configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Octopus API key not configured",
        )
    return await octopus_client.get_rate_plan()


@router.get("/consumption")
async def octopus_consumption(_: SessionData = Depends(require_viewer)) -> dict:
    if not octopus_client.configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Octopus not configured",
        )
    return {"results": await octopus_client.get_consumption()}


@router.get("/meter-power", response_model=OctopusMeterPower)
async def octopus_meter_power(_: SessionData = Depends(require_viewer)) -> OctopusMeterPower:
    return await octopus_client.get_meter_power_estimate()


@router.get("/dispatches")
async def octopus_dispatches(_: SessionData = Depends(require_viewer)) -> dict:
    if not octopus_client.configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Octopus not configured",
        )
    response = await octopus_client.get_dispatches()
    return response.model_dump(mode="json")


@router.get("/account")
async def octopus_account(_: SessionData = Depends(require_viewer)) -> dict:
    if not octopus_client.configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Octopus not configured",
        )
    return await octopus_client.get_account()


@router.get("/settings", response_model=OctopusConfigStatus)
async def get_octopus_settings(
    _: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OctopusConfigStatus:
    return await octopus_settings_service.get_status(db)


@router.put("/settings", response_model=OctopusConfigStatus)
async def update_octopus_settings(
    request: Request,
    body: OctopusConfig,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OctopusConfigStatus:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    status_result = await octopus_settings_service.set_config(db, body)
    await audit_service.record(
        db,
        username=session.username,
        role=session.role,
        action="update_octopus_settings",
        request_payload={
            "account_number": body.account_number,
            "mpan": body.mpan,
            "meter_serial": body.meter_serial,
            "region": body.region,
            "api_key_set": bool(body.api_key),
        },
        validation_result="valid",
        adapter_response=None,
        outcome=AuditOutcome.SUCCESS,
    )
    return status_result


@router.post("/discover", response_model=OctopusDiscoverResult)
async def discover_octopus(
    request: Request,
    body: OctopusDiscoverRequest,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OctopusDiscoverResult:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    try:
        result = await octopus_client.discover(body.api_key, body.account_number)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Octopus rejected the API key.",
            ) from exc
        if code == 404:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account number not found for this API key.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Octopus API error during discovery.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the Octopus API.",
        ) from exc
    return OctopusDiscoverResult(**result)
