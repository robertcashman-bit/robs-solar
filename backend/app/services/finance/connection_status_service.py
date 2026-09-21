"""One-shot Connections status — single app_settings round-trip."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettingRow
from app.schemas.finance import (
    FinanceConnectionStatuses,
    FundingCircleConfig,
    FundingCircleConfigStatus,
    LunchFlowConfig,
    LunchFlowConfigStatus,
    QuickFileConfig,
    QuickFileConfigStatus,
)
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.quickfile_settings_service import (
    _config_complete,
    quickfile_settings_service,
)
from app.services.settings_crypto import open_json

logger = logging.getLogger(__name__)

# Keys read in one IN() query for Connections. Keep in sync with the settings
# services — status GETs must not fan out into per-key Neon round-trips on a
# cold serverless isolate.
_BUNDLE_KEYS = (
    "quickfile",
    "quickfile_last_sync_at",
    "quickfile_last_error",
    "quickfile_quota_exhausted_at",
    "quickfile_budget_account_ids",
    "lunchflow",
    "lunch_flow",
    "lunchflow_last_sync_at",
    "lunch_flow_last_sync_at",
    "lunchflow_last_test_at",
    "lunch_flow_last_test_at",
    "funding_circle",
    "funding_circle_last_sync_at",
)


def _first(rows: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = rows.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _quickfile_from_rows(rows: dict[str, str]) -> QuickFileConfigStatus:
    env = quickfile_settings_service._env_config()
    raw = rows.get("quickfile")
    stored = quickfile_settings_service._read_stored(raw)
    if stored is None:
        config = env
    else:
        config = QuickFileConfig(
            account_number=stored.account_number or env.account_number,
            api_key=stored.api_key or env.api_key,
            application_id=stored.application_id or env.application_id,
        )
    configured = _config_complete(config)
    budget_ids: list[str] = []
    budget_raw = rows.get("quickfile_budget_account_ids")
    if budget_raw and str(budget_raw).strip():
        try:
            data = json.loads(budget_raw)
            if isinstance(data, list):
                budget_ids = [str(item) for item in data if str(item).strip()]
        except json.JSONDecodeError:
            budget_ids = []
    error_raw = rows.get("quickfile_last_error")
    quota_raw = rows.get("quickfile_quota_exhausted_at")
    return QuickFileConfigStatus(
        account_number=config.account_number,
        api_key_set=bool(config.api_key),
        application_id=config.application_id,
        configured=configured,
        connected=configured,
        last_sync_at=rows.get("quickfile_last_sync_at") or None,
        budget_account_external_ids=budget_ids,
        last_error=error_raw if error_raw and error_raw.strip() else None,
        quota_exhausted_at=quota_raw if quota_raw and quota_raw.strip() else None,
    )


def _lunchflow_from_rows(rows: dict[str, str]) -> LunchFlowConfigStatus:
    env = lunchflow_settings_service._env_config()
    raw = _first(rows, "lunchflow", "lunch_flow")
    if raw is None:
        config = env
    else:
        try:
            stored = LunchFlowConfig.model_validate(open_json(raw))
            config = LunchFlowConfig(api_key=stored.api_key or env.api_key)
        except Exception:
            logger.warning("Lunch Flow settings row unreadable — using env", exc_info=True)
            config = env
    configured = bool(config.api_key)
    sync = _first(rows, "lunchflow_last_sync_at", "lunch_flow_last_sync_at")
    tested = _first(rows, "lunchflow_last_test_at", "lunch_flow_last_test_at")
    return LunchFlowConfigStatus(
        api_key_set=configured,
        configured=configured,
        connected=bool(sync or tested),
        last_sync_at=sync,
    )


def _funding_circle_from_rows(rows: dict[str, str]) -> FundingCircleConfigStatus:
    raw = rows.get("funding_circle")
    if raw is None or not str(raw).strip():
        config = FundingCircleConfig()
    else:
        try:
            config = FundingCircleConfig.model_validate(json.loads(raw))
        except Exception:
            logger.warning("Funding Circle settings row unreadable", exc_info=True)
            config = FundingCircleConfig()
    last_sync = rows.get("funding_circle_last_sync_at") or None
    configured = config.outstanding_gbp is not None or bool(config.last_source)
    return FundingCircleConfigStatus(
        configured=configured,
        auto_sync=config.auto_sync,
        outstanding_gbp=config.outstanding_gbp,
        original_gbp=config.original_gbp,
        apr_pct=config.apr_pct,
        minimum_payment_gbp=config.minimum_payment_gbp,
        payment_day=config.payment_day,
        last_sync_at=last_sync,
        last_source=config.last_source,
        last_txn_on=config.last_txn_on,
        message=config.message,
    )


def _env_only_bundle() -> FinanceConnectionStatuses:
    """Degraded payload when Neon is unreachable — still unlocks the Connections UI."""
    qf = quickfile_settings_service._env_config()
    qf_ok = _config_complete(qf)
    lf_ok = lunchflow_settings_service.env_configured()
    return FinanceConnectionStatuses(
        lunchflow=LunchFlowConfigStatus(
            api_key_set=lf_ok,
            configured=lf_ok,
            connected=False,
            last_sync_at=None,
        ),
        quickfile=QuickFileConfigStatus(
            account_number=qf.account_number,
            api_key_set=bool(qf.api_key),
            application_id=qf.application_id,
            configured=qf_ok,
            connected=qf_ok,
            last_sync_at=None,
        ),
        funding_circle=FundingCircleConfigStatus(),
    )


async def load_connection_statuses(db: AsyncSession) -> FinanceConnectionStatuses:
    """Return LF + QF + FC status from one app_settings SELECT.

    Prefer a partial/env fallback over hanging the Connections page when Neon
    is slow or the isolate is still warming.
    """
    try:
        result = await db.execute(
            select(AppSettingRow).where(AppSettingRow.key.in_(_BUNDLE_KEYS))
        )
        rows = {row.key: row.value for row in result.scalars().all()}
        return FinanceConnectionStatuses(
            lunchflow=_lunchflow_from_rows(rows),
            quickfile=_quickfile_from_rows(rows),
            funding_circle=_funding_circle_from_rows(rows),
        )
    except Exception:
        logger.warning(
            "connection-status bundle failed — returning env-only partial status",
            exc_info=True,
        )
        return _env_only_bundle()


def light_integration_flags() -> dict[str, Any]:
    """Env-only integration hints for ``/finance/health?light=1`` (no Neon reads)."""
    qf = quickfile_settings_service.env_configured()
    lf = lunchflow_settings_service.env_configured()
    return {
        "quickfile": {
            "configured": qf,
            "connected": qf,
            "last_sync_at": None,
        },
        "lunchflow": {
            "configured": lf,
            "connected": False,
            "last_sync_at": None,
        },
        "finance_bank_reads_ready": bool(qf or lf),
    }
