import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me"
    database_url: str = "sqlite+aiosqlite:///./data/robs_solar.db"
    read_only: bool = True
    adapter_mode: str = "simulator"
    cors_origins: str = "http://127.0.0.1:3000"
    admin_username: str = "admin"
    admin_password: str = "change-me-admin"
    admin_email: str = "robertdavidcashman@gmail.com"
    viewer_username: str = "viewer"
    viewer_password: str = "change-me-viewer"
    rate_limit_writes_per_minute: int = 10
    default_poll_interval_seconds: int = 5

    ha_base_url: str = ""
    ha_token: str = ""
    ha_entity_pv_power: str = ""
    ha_entity_battery_soc: str = ""
    ha_entity_house_load: str = ""
    ha_entity_grid_import: str = ""
    ha_entity_grid_export: str = ""
    ha_entity_inverter_mode: str = ""
    ha_entity_inverter_status: str = ""
    ha_entity_export_limit: str = ""
    ha_service_export_limit: str = ""
    ha_service_schedule: str = ""
    ha_service_operating_mode: str = ""

    modbus_bridge_url: str = ""
    modbus_bridge_token: str = ""
    modbus_bridge_writes_enabled: bool = False

    # Direct Modbus TCP (RS485-WiFi dongle)
    modbus_host: str = ""
    modbus_port: int = 502
    modbus_slave_id: int = 1
    modbus_max_retries: int = 2
    poll_interval_live_seconds: int = 10
    poll_interval_energy_seconds: int = 60

    # Octopus Energy (API key only — never store account password)
    octopus_api_key: str = ""
    octopus_account_number: str = ""
    octopus_mpan: str = ""
    octopus_meter_serial: str = ""
    octopus_device_id: str = ""
    octopus_tariff: str = "AGILE"
    octopus_region: str = "C"

    # Solar forecast (Open-Meteo)
    forecast_latitude: float = 51.5074
    forecast_longitude: float = -0.1278
    panel_count_ew: int = 16
    panel_count_w: int = 6
    panel_wattage: int = 480

    # Global write feature flag. Even when read_only is false, live (non-simulator)
    # adapters will refuse to write unless this is explicitly enabled.
    enable_live_writes: bool = False

    # Sunsynk Connect / Connect Pro cloud adapter (primary live integration path).
    # NOTE: the Sunsynk cloud HTTP API is community-inferred and UNVERIFIED.
    # Primary Sunsynk Connect API host (matches www.sunsynk.net web app).
    sunsynk_base_url: str = "https://api.sunsynk.net"
    sunsynk_username: str = ""
    sunsynk_password: str = ""
    # One-shot emailed Sunsynk lockout code. Consumed on the next login attempt.
    sunsynk_verification_code: str = ""
    sunsynk_plant_id: str = ""
    sunsynk_inverter_sn: str = ""
    sunsynk_enable_unverified_writes: bool = False
    sunsynk_timeout_seconds: float = 10.0
    sunsynk_max_retries: int = 2

    # Metric sampling (read-only background task)
    metrics_sampler_enabled: bool = True
    metrics_sample_interval_seconds: int = 60
    metrics_retention_days: int = 90

    # Read-only inverter settings watcher (detects external/app changes; never writes)
    settings_watch_enabled: bool = True
    # Poll settings every N metric samples (default 3 → ~3 minutes at 60s sampling)
    settings_watch_every_n_samples: int = 3
    settings_watch_retention_days: int = 90

    # Default tariff (GBP per kWh); overridable via PUT /tariff
    tariff_import_rate: float = 0.28
    tariff_export_rate: float = 0.15
    tariff_currency: str = "GBP"

    # Optional alert notifications (webhook only — no SMTP in MVP)
    alert_webhook_url: str = ""

    # IOG off-peak unit rate (GBP/kWh) for reconciliation billing split
    iog_offpeak_rate_gbp: float = 0.07

    # Intelligent Octopus Go off-peak window (local time, HH:MM)
    iog_offpeak_start: str = "23:30"
    iog_offpeak_end: str = "05:30"

    # Tariff timezone. All cheap/peak window and TOU band times are interpreted in
    # this zone, NOT the server's local zone, so a backend running in UTC (Render,
    # Vercel, containers) still aligns the schedule to the user's wall clock and
    # follows daylight-saving transitions.
    tariff_timezone: str = "Europe/London"

    # Battery auto-align to IOG cheap windows (opt-in; default off)
    auto_schedule_enabled: bool = False
    auto_schedule_interval_minutes: int = 15
    # Daytime battery discharge floor (reserve SOC). The battery is allowed to
    # discharge down to this SOC during the day; it must stay well below a full
    # battery so stored energy actually covers the house load instead of importing.
    auto_schedule_soc_floor_pct: int = 20
    # Target SOC to reach during the overnight cheap-rate charge window.
    auto_schedule_overnight_target_pct: int = 100
    # Highest daytime floor we will accept. A floor at/above this would keep the
    # battery effectively full all day (the "stuck at 95%" failure mode).
    max_daytime_floor_pct: int = 90

    # Peak import guard — auto-correct grid import at peak rate when battery is high SOC.
    peak_import_guard_enabled: bool = True
    peak_import_guard_threshold_w: float = 100.0
    peak_import_guard_cooldown_minutes: int = 30
    peak_import_guard_sustained_samples: int = 2

    # Sell-to-grid advisor. Worth selling when the export rate clears the
    # threshold and the battery is above the reserve floor (so we don't sell
    # energy we'd need at the expensive peak).
    sell_export_threshold_gbp: float = 0.15
    sell_min_soc_pct: int = 50
    battery_capacity_kwh: float = 16.1

    # AI assistant (OpenAI). Key lives only on the backend; never sent to the UI.
    # The assistant is read-only by design: it proposes changes that an admin must
    # confirm. Applying a change reuses the audited /controls/* endpoints.
    openai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_enabled: bool = False
    ai_timeout_seconds: float = 30.0

    # QuickFile (business finance sync — same credentials as Custody Note)
    quickfile_account_number: str = ""
    quickfile_api_key: str = ""
    quickfile_application_id: str = ""

    # Open Banking (TrueLayer — UK)
    truelayer_client_id: str = ""
    truelayer_client_secret: str = ""
    truelayer_redirect_uri: str = ""
    truelayer_environment: str = "sandbox"
    lunchflow_api_key: str = ""
    # Vercel Cron bearer for /finance/cron/daily-sync
    cron_secret: str = ""
    # Automatic web backup (Vercel Blob). Never required for local/tests.
    blob_read_write_token: str = ""
    finance_backup_prefix: str = "robs-finance-backups"

    # Tesla Fleet API (EV charging visibility)
    tesla_client_id: str = ""
    tesla_client_secret: str = ""
    tesla_refresh_token: str = ""
    tesla_energy_site_id: str = ""

    # OIDC SSO (optional — local password auth remains available)
    oidc_enabled: bool = False
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""
    oidc_admin_emails: str = ""

    # Magic-code (email OTP) sign-in
    magic_code_enabled: bool = True
    magic_code_ttl_seconds: int = 600
    magic_code_admin_emails: str = ""
    magic_code_viewer_emails: str = ""
    # Always used in sign-in emails. Never a Cloudflare tunnel or preview host.
    public_app_url: str = "https://robs-solar.vercel.app"
    # Resend transactional email (preferred). When unset, codes are logged and
    # returned in the API response for local/dev only (never in production).
    resend_api_key: str = ""
    resend_from_email: str = "Rob's Finance <onboarding@resend.dev>"


    @model_validator(mode="after")
    def _alias_legacy_env_names(self) -> "Settings":
        # Previous commits and the live Vercel project use LUNCH_FLOW_API_KEY.
        if not self.lunchflow_api_key.strip():
            alt = os.environ.get("LUNCH_FLOW_API_KEY", "").strip()
            if alt:
                self.lunchflow_api_key = alt
        if not self.blob_read_write_token.strip():
            alt_blob = (
                os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
                or os.environ.get("VERCEL_BLOB_READ_WRITE_TOKEN", "").strip()
            )
            if alt_blob:
                self.blob_read_write_token = alt_blob
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        # Hosted Finance and local app must always be able to call /backend.
        # A leftover localhost-only CORS_ORIGINS on Vercel blocked browser login.
        for extra in (
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "https://robs-solar.vercel.app",
        ):
            if extra not in origins:
                origins.append(extra)
        return origins

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production

    @property
    def oidc_admin_email_list(self) -> list[str]:
        return [
            email.strip().lower()
            for email in self.oidc_admin_emails.split(",")
            if email.strip()
        ]

    @property
    def magic_code_admin_email_list(self) -> list[str]:
        emails = [
            email.strip().lower()
            for email in self.magic_code_admin_emails.split(",")
            if email.strip()
        ]
        # Fall back to OIDC admin allowlist when magic-code list is empty.
        resolved = emails or list(self.oidc_admin_email_list)
        admin_email = self.admin_email.strip().lower()
        if admin_email and "@" in admin_email and admin_email not in resolved:
            resolved.append(admin_email)
        return resolved

    @property
    def magic_code_viewer_email_list(self) -> list[str]:
        return [
            email.strip().lower()
            for email in self.magic_code_viewer_emails.split(",")
            if email.strip()
        ]


    @property
    def truelayer_auth_base(self) -> str:
        return (
            "https://auth.truelayer.com"
            if self.truelayer_environment.lower() == "live"
            else "https://auth.truelayer-sandbox.com"
        )

    @property
    def truelayer_api_base(self) -> str:
        return (
            "https://api.truelayer.com"
            if self.truelayer_environment.lower() == "live"
            else "https://api.truelayer-sandbox.com"
        )

    @property
    def cookie_samesite(self) -> str:
        return "lax"


settings = Settings()


def get_settings() -> Settings:
    return settings
