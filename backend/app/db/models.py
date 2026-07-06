from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[str] = mapped_column(Text, nullable=False)
    validation_result: Mapped[str] = mapped_column(String(256), nullable=False)
    adapter_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)


class ConfigSnapshotRow(Base):
    __tablename__ = "config_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class MetricSampleRow(Base):
    __tablename__ = "metric_samples"
    __table_args__ = (Index("ix_metric_samples_timestamp", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pv_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    battery_soc_pct: Mapped[float] = mapped_column(Float, nullable=False)
    house_load_w: Mapped[float] = mapped_column(Float, nullable=False)
    grid_import_w: Mapped[float] = mapped_column(Float, nullable=False)
    grid_export_w: Mapped[float] = mapped_column(Float, nullable=False)
    daily_pv_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    daily_import_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    daily_export_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    adapter_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    data_source: Mapped[str] = mapped_column(String(16), nullable=False)
    pv1_power_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pv2_power_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_power_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_voltage_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_current_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_soh_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grid_voltage_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grid_frequency_hz: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_battery_charge_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_battery_discharge_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class AppSettingRow(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class AlertRow(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    acknowledged: Mapped[bool] = mapped_column(default=False, nullable=False)


class DailySavingsRow(Base):
    __tablename__ = "daily_savings"
    __table_args__ = (Index("ix_daily_savings_date", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    solar_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    house_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    import_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    export_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    battery_charge_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    battery_discharge_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_cost_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_no_solar_cost_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_saving_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    export_credit_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    standing_charge_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    optimisation_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    recommendations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OptimisationRecommendationRow(Base):
    __tablename__ = "optimisation_recommendations"
    __table_args__ = (Index("ix_opt_recs_date", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    current_setting: Mapped[str] = mapped_column(String(256), nullable=False)
    proposed_setting: Mapped[str] = mapped_column(String(256), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_extra_saving_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    manual_instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rollback_value: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    calculation_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    can_auto_apply: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class FinanceAccountRow(Base):
    __tablename__ = "finance_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    balance_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    credit_limit_gbp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    interest_rate_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    minimum_payment_gbp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceLiabilityRow(Base):
    __tablename__ = "finance_liabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    debt_type: Mapped[str] = mapped_column(String(32), nullable=False)
    balance_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    interest_rate_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    minimum_payment_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    overpayment_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payment_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PersonalFinanceSnapshotRow(Base):
    __tablename__ = "personal_finance_snapshots"
    __table_args__ = (Index("ix_personal_finance_snapshots_date", "snapshot_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[str] = mapped_column(String(10), nullable=False)
    monthly_income_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    monthly_spending_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    household_bills_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    debt_repayments_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    surplus_deficit_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BusinessFinanceSnapshotRow(Base):
    __tablename__ = "business_finance_snapshots"
    __table_args__ = (Index("ix_business_finance_snapshots_date", "snapshot_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[str] = mapped_column(String(10), nullable=False)
    turnover_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expenses_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vat_reserve_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    corp_tax_reserve_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    debtors_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    creditors_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    profit_estimate_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cash_available_to_draw_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MonthlyBudgetRow(Base):
    __tablename__ = "monthly_budget"
    __table_args__ = (Index("ix_monthly_budget_scope_month", "scope", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    budgeted_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CashflowForecastRow(Base):
    __tablename__ = "cashflow_forecast"
    __table_args__ = (Index("ix_cashflow_forecast_date", "forecast_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    forecast_date: Mapped[str] = mapped_column(String(10), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceInsightRow(Base):
    __tablename__ = "finance_insights"
    __table_args__ = (Index("ix_finance_insights_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    related_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class EnergyDailySnapshotRow(Base):
    __tablename__ = "energy_daily_snapshots"
    __table_args__ = (Index("ix_energy_daily_snapshots_date", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    pv_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    import_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    export_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    battery_charge_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    battery_discharge_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_soc_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    savings_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    export_credit_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    peak_discharge_ok: Mapped[bool] = mapped_column(default=True, nullable=False)
    alerts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceTransactionRow(Base):
    __tablename__ = "finance_transactions"
    __table_args__ = (Index("ix_finance_transactions_external_id", "external_id", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    transaction_date: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    merchant: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    amount_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    reference: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    is_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SolarSettingsRow(Base):
    __tablename__ = "solar_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    export_threshold_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    alert_battery_peak: Mapped[bool] = mapped_column(default=True, nullable=False)
    alert_savings_below_forecast: Mapped[bool] = mapped_column(default=True, nullable=False)
    display_preferences_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
