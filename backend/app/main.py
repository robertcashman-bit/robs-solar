from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.passwords import warn_if_default_passwords
from app.config import settings
from app.db.session import init_db
from app.logging import configure_logging
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes import (
    ai,
    alerts,
    audit,
    auth,
    capabilities,
    config_safety,
    config_snapshots,
    controls,
    forecast,
    health,
    metrics,
    octopus,
    optimisation,
    recommendations,
    settings_notifications,
    tariff,
    ws,
)
from app.services.auto_scheduler import start_auto_scheduler, stop_auto_scheduler
from app.services.metric_sampler import start_sampler, stop_sampler


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    warn_if_default_passwords()
    await init_db()
    await _load_octopus_credentials()
    start_sampler()
    start_auto_scheduler()
    yield
    await stop_auto_scheduler()
    await stop_sampler()


async def _load_octopus_credentials() -> None:
    from app.db.session import SessionLocal
    from app.services.octopus_client import octopus_client
    from app.services.octopus_settings_service import octopus_settings_service
    from app.services.safety_settings_service import safety_settings_service

    async with SessionLocal() as db:
        await octopus_settings_service.load_into_client(db)
        await safety_settings_service.load_cache(db)
    if octopus_client.configured() and octopus_client.credentials.account_number:
        try:
            await octopus_client.resolve_tariffs_from_account()
        except Exception:
            pass


app = FastAPI(title="Rob's Solar API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(capabilities.router)
app.include_router(metrics.router)
app.include_router(audit.router)
app.include_router(controls.router)
app.include_router(config_snapshots.router)
app.include_router(tariff.router)
app.include_router(octopus.router)
app.include_router(recommendations.router)
app.include_router(optimisation.router)
app.include_router(forecast.router)
app.include_router(alerts.router)
app.include_router(settings_notifications.router)
app.include_router(config_safety.router)
app.include_router(ai.router)
app.include_router(ws.router)
