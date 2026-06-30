from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class UserRole(str, Enum):
    ADMIN = "admin"
    VIEWER = "viewer"


class InverterMode(str, Enum):
    SELF_USE = "self_use"
    BACKUP = "backup"
    FEED_IN = "feed_in"
    OFF_GRID = "off_grid"


class InverterStatus(str, Enum):
    ONLINE = "online"
    STANDBY = "standby"
    FAULT = "fault"
    OFFLINE = "offline"


class SystemWorkMode(str, Enum):
    """Sunsynk register 232 work modes."""

    SELLING = "selling"
    BYPASS = "bypass"
    BATTERY_FIRST = "battery_first"


def work_mode_to_inverter_mode(mode: SystemWorkMode) -> InverterMode:
    mapping = {
        SystemWorkMode.SELLING: InverterMode.FEED_IN,
        SystemWorkMode.BYPASS: InverterMode.BACKUP,
        SystemWorkMode.BATTERY_FIRST: InverterMode.SELF_USE,
    }
    return mapping[mode]


def inverter_mode_to_work_mode(mode: InverterMode) -> SystemWorkMode:
    mapping = {
        InverterMode.FEED_IN: SystemWorkMode.SELLING,
        InverterMode.BACKUP: SystemWorkMode.BYPASS,
        InverterMode.SELF_USE: SystemWorkMode.BATTERY_FIRST,
        InverterMode.OFF_GRID: SystemWorkMode.BATTERY_FIRST,
    }
    return mapping.get(mode, SystemWorkMode.BATTERY_FIRST)


class LiveMetrics(BaseModel):
    pv_power_w: float = Field(ge=0)
    battery_soc_pct: float = Field(ge=0, le=100)
    battery_power_w: Optional[float] = None
    house_load_w: float = Field(ge=0)
    grid_import_w: float = Field(ge=0)
    grid_export_w: float = Field(ge=0)
    inverter_mode: InverterMode
    inverter_status: InverterStatus
    daily_pv_kwh: float = Field(ge=0)
    daily_import_kwh: float = Field(ge=0)
    daily_export_kwh: float = Field(ge=0)
    timestamp: datetime
    # Extended Modbus fields (optional — absent for cloud/simulator adapters)
    pv1_power_w: Optional[float] = Field(default=None, ge=0)
    pv2_power_w: Optional[float] = Field(default=None, ge=0)
    battery_voltage_v: Optional[float] = Field(default=None, ge=0)
    battery_current_a: Optional[float] = Field(default=None)
    battery_temp_c: Optional[float] = None
    battery_soh_pct: Optional[float] = Field(default=None, ge=0, le=100)
    grid_voltage_v: Optional[float] = Field(default=None, ge=0)
    grid_frequency_hz: Optional[float] = Field(default=None, ge=0)
    daily_battery_charge_kwh: Optional[float] = Field(default=None, ge=0)
    daily_battery_discharge_kwh: Optional[float] = Field(default=None, ge=0)
    system_work_mode: Optional[SystemWorkMode] = None


class ConnectivityStatus(BaseModel):
    backend_healthy: bool
    adapter_mode: str
    adapter_connected: bool
    last_successful_poll: Optional[datetime] = None
    degraded_reason: Optional[str] = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserInfo(BaseModel):
    username: str
    role: UserRole


class LoginResponse(BaseModel):
    user: UserInfo
    csrf_token: str


class SessionResponse(BaseModel):
    user: UserInfo
    csrf_token: str


class HealthResponse(BaseModel):
    status: str
    adapter_mode: str
    read_only: bool
    timestamp: datetime


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    REJECTED = "rejected"
    FAILED = "failed"
    VALIDATION_ERROR = "validation_error"


class AuditEntry(BaseModel):
    id: int
    timestamp: datetime
    username: str
    role: UserRole
    action: str
    request_payload: dict[str, Any]
    validation_result: str
    adapter_response: Optional[str] = None
    outcome: AuditOutcome


class AuditListResponse(BaseModel):
    entries: list[AuditEntry]
    total: int


class ExportLimitRequest(BaseModel):
    limit_w: int = Field(ge=0, le=8000)

    @field_validator("limit_w")
    @classmethod
    def validate_step(cls, value: int) -> int:
        if value % 100 != 0:
            raise ValueError("limit_w must be a multiple of 100")
        return value


class ScheduleAction(str, Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"


class ScheduleWindow(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    action: ScheduleAction
    power_w: Optional[int] = Field(default=None, ge=0, le=10000)
    target_soc_pct: Optional[int] = Field(default=None, ge=0, le=100)
    grid_charge_enabled: Optional[bool] = None


class TouBand(BaseModel):
    slot: int = Field(ge=1, le=6)
    start: str
    end: str
    target_soc_pct: Optional[int] = Field(default=None, ge=0, le=100)
    grid_charge_enabled: bool = False
    power_w: Optional[int] = Field(default=None, ge=0, le=10000)


class InverterSettingsResponse(BaseModel):
    inverter_sn: str = ""
    plant_id: str = ""
    plant_name: str = ""
    plant_permissions: list[str] = Field(default_factory=list)
    write_allowed: bool = False
    write_denied_reason: str = ""
    sys_work_mode: str = ""
    sys_work_mode_label: str = ""
    energy_mode: str = ""
    solar_sell: bool = False
    export_limit_mode: str = ""
    discharge_current_a: Optional[int] = None
    bands: list[TouBand] = Field(default_factory=list)
    active_band_slot: Optional[int] = None
    active_band: Optional[TouBand] = None
    diagnosis: str = ""


class ScheduleRequest(BaseModel):
    windows: list[ScheduleWindow] = Field(min_length=1, max_length=24)


class TouBandWrite(BaseModel):
    """A single editable TOU band sent from the control UI."""

    slot: int = Field(ge=1, le=6)
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    target_soc_pct: Optional[int] = Field(default=None, ge=0, le=100)
    grid_charge_enabled: bool = False
    power_w: Optional[int] = Field(default=None, ge=0, le=10000)


class TouBandsRequest(BaseModel):
    bands: list[TouBandWrite] = Field(min_length=1, max_length=6)


class OperatingModeRequest(BaseModel):
    mode: InverterMode


class BatteryControlRequest(BaseModel):
    charge_current_a: Optional[int] = Field(default=None, ge=0, le=190)
    discharge_current_a: Optional[int] = Field(default=None, ge=0, le=190)
    grid_charge_current_a: Optional[int] = Field(default=None, ge=0, le=50)


class ForceBatteryAction(str, Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    STOP = "stop"


class ForceBatteryRequest(BaseModel):
    action: ForceBatteryAction


class ControlWriteResult(BaseModel):
    success: bool
    message: str
    audit_id: int
    applied_value: Optional[dict[str, Any]] = None
    verified: bool = False
    verification_pending: bool = False
    verification_message: str = ""


class RestoreResult(BaseModel):
    success: bool
    message: str
    audit_id: int
    restored_snapshot_id: Optional[int] = None


class AdapterCapabilities(BaseModel):
    mode: str
    supports_read: bool
    supports_write: bool
    supported_writes: list[str]
    notes: list[str] = Field(default_factory=list)


class SystemCapabilitiesResponse(BaseModel):
    adapter: AdapterCapabilities
    data_source: str
    read_only: bool
    enable_live_writes: bool
    sunsynk_enable_unverified_writes: bool
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    modbus_host: Optional[str] = None
    modbus_port: Optional[int] = None
    modbus_slave_id: Optional[int] = None
    poll_interval_live_seconds: Optional[int] = None
    poll_interval_energy_seconds: Optional[int] = None
    octopus_configured: bool = False


class AdapterError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class UnsupportedWriteError(AdapterError):
    pass


class HistoryRange(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class MetricHistoryPoint(BaseModel):
    timestamp: datetime
    pv_power_w: float
    battery_soc_pct: float
    house_load_w: float
    grid_import_w: float
    grid_export_w: float
    battery_soh_pct: Optional[float] = None


class MetricHistoryResponse(BaseModel):
    range: HistoryRange
    points: list[MetricHistoryPoint]


class MetricSummaryResponse(BaseModel):
    range: HistoryRange
    pv_kwh: float
    consumption_kwh: float
    import_kwh: float
    export_kwh: float
    self_consumption_pct: float
    import_cost: float
    export_credit: float
    net_cost: float
    estimated_cost_without_solar: float
    savings: float
    currency: str


class MetricCompareDelta(BaseModel):
    label: str
    today: float
    yesterday: float
    unit: str
    higher_is_better: bool


class MetricCompareResponse(BaseModel):
    today: MetricSummaryResponse
    yesterday: MetricSummaryResponse
    deltas: list[MetricCompareDelta]


class TariffSettings(BaseModel):
    import_rate: float = Field(ge=0, le=10)
    export_rate: float = Field(ge=0, le=10)
    currency: str = Field(min_length=3, max_length=3)


class OctopusConfig(BaseModel):
    """Octopus credentials submitted by an admin (PUT /octopus/settings)."""

    api_key: str = Field(default="", max_length=128)
    account_number: str = Field(default="", max_length=32)
    mpan: str = Field(default="", max_length=21)
    meter_serial: str = Field(default="", max_length=32)
    region: str = Field(default="C", max_length=1)


class OctopusConfigStatus(BaseModel):
    """Masked Octopus config returned to the client (never leaks the key)."""

    api_key_set: bool = False
    account_number: str = ""
    mpan: str = ""
    meter_serial: str = ""
    region: str = "C"
    configured: bool = False


class OctopusDiscoverRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=128)
    account_number: str = Field(min_length=1, max_length=32)


class OctopusDiscoverResult(BaseModel):
    account_number: str = ""
    mpan: str = ""
    meter_serial: str = ""
    region: str = ""
    import_tariff_code: str = ""


class OctopusTariffResponse(BaseModel):
    import_tariff_code: str = ""
    import_product_code: str = ""
    import_display_name: str = ""
    import_rate_pence: Optional[float] = None
    export_tariff_code: str = ""
    export_product_code: str = ""
    export_display_name: str = ""
    export_rate_pence: Optional[float] = None
    standing_charge_pence: Optional[float] = None
    is_variable: bool = False
    tariff_family: str = ""
    region: str = ""


class DispatchWindow(BaseModel):
    start: datetime
    end: datetime
    source: str = ""
    delta_kwh: Optional[float] = None


class OffPeakWindow(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class DispatchResponse(BaseModel):
    off_peak_window: OffPeakWindow
    planned: list[DispatchWindow] = Field(default_factory=list)
    completed: list[DispatchWindow] = Field(default_factory=list)
    tariff_family: str = ""


class AutoScheduleConfigRequest(BaseModel):
    enabled: bool
    soc_floor_pct: Optional[int] = Field(default=None, ge=0, le=100)


class AutoScheduleStatus(BaseModel):
    enabled: bool
    soc_floor_pct: int
    last_run_at: Optional[datetime] = None
    last_run_message: str = ""
    last_write_audit_id: Optional[int] = None
    next_cheap_windows: list[DispatchWindow] = Field(default_factory=list)
    computed_bands: list[TouBandWrite] = Field(default_factory=list)


class ReconciliationInterval(BaseModel):
    start: datetime
    end: datetime
    consumption_kwh: float
    is_cheap: bool


class ReconciliationResponse(BaseModel):
    range: HistoryRange
    meter_import_kwh: float
    cheap_import_kwh: float
    day_import_kwh: float
    export_kwh: float
    import_cost_gbp: float
    export_earnings_gbp: float
    net_bill_impact_gbp: float
    inverter_estimate_gbp: float
    delta_gbp: float
    currency: str = "GBP"
    intervals: list[ReconciliationInterval] = Field(default_factory=list)
    configured: bool = False
    message: str = ""


class NotificationCategoryToggle(BaseModel):
    soc_low: bool = True
    soc_high: bool = False
    import_high: bool = True
    offline: bool = True
    negative_price: bool = True
    price_spike: bool = True
    dispatch_available: bool = True
    export_price_high: bool = True
    soc_low_before_offpeak: bool = True
    inverter_fault: bool = True


class NotificationSettings(BaseModel):
    webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_to: str = ""
    export_price_threshold_pence: float = 20.0
    categories: NotificationCategoryToggle = Field(default_factory=NotificationCategoryToggle)


class NotificationSettingsStatus(BaseModel):
    webhook_url_set: bool = False
    smtp_configured: bool = False
    email_to: str = ""
    export_price_threshold_pence: float = 20.0
    categories: NotificationCategoryToggle = Field(default_factory=NotificationCategoryToggle)


class EvStatusResponse(BaseModel):
    car_charging_likely: bool = False
    in_dispatch_window: bool = False
    house_load_w: float = 0.0
    message: str = ""


class RuleConditionType(str, Enum):
    SOC_BELOW = "soc_below"
    SOC_ABOVE = "soc_above"
    EXPORT_RATE_ABOVE = "export_rate_above"
    DISPATCH_ACTIVE = "dispatch_active"
    CAR_CHARGING = "car_charging"
    HOUR_BETWEEN = "hour_between"


class RuleActionType(str, Enum):
    FORCE_BATTERY_CHARGE = "force_battery_charge"
    FORCE_BATTERY_DISCHARGE = "force_battery_discharge"
    FORCE_BATTERY_STOP = "force_battery_stop"
    SET_AUTO_SCHEDULE = "set_auto_schedule"
    RAISE_ALERT = "raise_alert"


class AutomationRule(BaseModel):
    id: str
    name: str
    enabled: bool = True
    condition: RuleConditionType
    condition_value: float = 0.0
    condition_value_end: Optional[float] = None
    action: RuleActionType
    action_value: Optional[bool] = None
    cooldown_minutes: int = 30


class AutomationRulesResponse(BaseModel):
    rules: list[AutomationRule] = Field(default_factory=list)


class SafetySettings(BaseModel):
    read_only: bool
    enable_live_writes: bool
    runtime_overrides: bool = False


class SafetySettingsUpdate(BaseModel):
    read_only: Optional[bool] = None
    enable_live_writes: Optional[bool] = None


# --- AI assistant -----------------------------------------------------------


class AiActionKind(str, Enum):
    """A proposed change the assistant can suggest. Each maps 1:1 to an existing
    audited control endpoint that the admin invokes on confirm."""

    SET_TOU_BANDS = "set_tou_bands"
    SET_EXPORT_LIMIT = "set_export_limit"
    SET_OPERATING_MODE = "set_operating_mode"
    SET_AUTO_SCHEDULE = "set_auto_schedule"


# Maps a proposed action to the control endpoint the frontend calls on confirm.
AI_ACTION_ENDPOINTS: dict[str, str] = {
    AiActionKind.SET_TOU_BANDS.value: "/controls/tou",
    AiActionKind.SET_EXPORT_LIMIT.value: "/controls/export-limit",
    AiActionKind.SET_OPERATING_MODE.value: "/controls/operating-mode",
    AiActionKind.SET_AUTO_SCHEDULE.value: "/controls/auto-schedule",
}


class AiProposedAction(BaseModel):
    kind: AiActionKind
    endpoint: str = ""
    summary: str
    reason: str
    body: dict[str, Any] = Field(default_factory=dict)


class AiAssessment(BaseModel):
    optimal: bool
    headline: str
    findings: list[str] = Field(default_factory=list)
    proposed_actions: list[AiProposedAction] = Field(default_factory=list)


class AiStatusResponse(BaseModel):
    enabled: bool
    model: str = ""
    reason: str = ""


class AiChatMessage(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class AiChatRequest(BaseModel):
    messages: list[AiChatMessage] = Field(min_length=1, max_length=20)


class AiChatResponse(BaseModel):
    reply: str
    proposed_actions: list[AiProposedAction] = Field(default_factory=list)
