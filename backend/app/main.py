import logging
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    warn_if_default_passwords()
    if settings.app_env.lower() == "production" and settings.adapter_mode.lower() == "simulator":
        logger.info(
            "APP_ENV=production with ADAPTER_MODE=simulator — "
            "solar adapter unused; finance uses Neon/local data"
        )
    await init_db()
    await _restore_finance_if_empty()
    await _seed_stated_finance()
    yield


async def _restore_finance_if_empty() -> None:
    from app.db.session import SessionLocal
    from app.services.finance.finance_backup_service import restore_latest_web_backup_if_empty

    try:
        async with SessionLocal() as db:
            restored = await restore_latest_web_backup_if_empty(db)
        if restored:
            logger.info("Restored finance books from web backup")
    except Exception:
        logger.exception("Finance web-backup restore skipped")


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
