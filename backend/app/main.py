import logging
from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.passwords import warn_if_default_passwords
from app.config import settings
from app.db.session import init_db
from app.logging import configure_logging
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.strip_backend_prefix import StripBackendPrefixMiddleware

# Finance-first surface. Solar/energy routers (sunsynk, octopus, metrics, controls,
# forecast, …) are intentionally not mounted — see ENERGY_FOLLOWUP.md.
from app.routes import auth, finance, health

logger = logging.getLogger(__name__)

# Cold Vercel Python + Neon must not sit in lifespan until the browser aborts
# Connections status GETs (~45s). Prefer a degraded start over a hung isolate.
_INIT_DB_TIMEOUT_S = 20.0
_POST_INIT_TIMEOUT_S = 15.0


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    warn_if_default_passwords()
    if settings.app_env.lower() == "production" and settings.adapter_mode.lower() == "simulator":
        logger.info(
            "APP_ENV=production with ADAPTER_MODE=simulator — "
            "solar adapter unused; finance uses Neon/local data"
        )
    try:
        await asyncio.wait_for(init_db(), timeout=_INIT_DB_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.error(
            "init_db timed out after %.0fs — serving with schema possibly incomplete",
            _INIT_DB_TIMEOUT_S,
        )
    except Exception:
        logger.exception("init_db failed — serving anyway so health/auth can answer")
    try:
        await asyncio.wait_for(_restore_finance_if_empty(), timeout=_POST_INIT_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("finance web-backup restore timed out — skipping")
    except Exception:
        logger.exception("Finance web-backup restore skipped")
    try:
        await asyncio.wait_for(_seed_stated_finance(), timeout=_POST_INIT_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("stated finance seed timed out — skipping")
    except Exception:
        logger.exception("stated finance seed skipped")
    yield


async def _restore_finance_if_empty() -> None:
    from app.db.session import SessionLocal
    from app.services.finance.finance_backup_service import restore_latest_web_backup_if_empty

    async with SessionLocal() as db:
        restored = await restore_latest_web_backup_if_empty(db)
    if restored:
        logger.info("Restored finance books from web backup")


async def _seed_stated_finance() -> None:
    from app.services.finance.cashflow_plan_service import ensure_overdraft_limits
    from app.services.finance.finance_seed_service import (
        ensure_clear_stale_mortgage_original,
        ensure_stated_house_share,
        ensure_stated_mortgage_half,
        ensure_stated_pension,
    )

    await ensure_stated_pension()
    await ensure_stated_mortgage_half()
    await ensure_clear_stale_mortgage_original()
    await ensure_stated_house_share()
    await ensure_overdraft_limits()


app = FastAPI(title="Rob's Finance API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://robs-solar(-[a-z0-9]+)?-robert-cashmans-projects\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(StripBackendPrefixMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(finance.router)
