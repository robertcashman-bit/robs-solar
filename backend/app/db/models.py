from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint
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
    __table_args__ = (Index("ix_finance_accounts_active_scope", "is_active", "scope"),)

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
    dla_direction: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceLiabilityRow(Base):
    __tablename__ = "finance_liabilities"
    __table_args__ = (Index("ix_finance_liabilities_active", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    debt_type: Mapped[str] = mapped_column(String(32), nullable=False)
    balance_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    interest_rate_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    minimum_payment_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    overpayment_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    original_balance_gbp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payment_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dla_direction: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    interest_rate_known: Mapped[bool] = mapped_column(default=True, nullable=False)
    credit_limit_gbp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
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


class FinancePositionSnapshotRow(Base):
    __tablename__ = "finance_position_snapshots"
    __table_args__ = (Index("ix_finance_position_snapshots_month", "month", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    total_debt_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    personal_debt_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    business_debt_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_worth_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cash_available_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceOverviewCacheRow(Base):
    __tablename__ = "finance_overview_cache"

    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
    __table_args__ = (
        Index("ix_cashflow_forecast_date", "forecast_date"),
        Index("ix_cashflow_forecast_confirmed_date", "is_confirmed", "forecast_date"),
    )

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


class SolarSettingsRow(Base):
    __tablename__ = "solar_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    export_threshold_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    alert_battery_peak: Mapped[bool] = mapped_column(default=True, nullable=False)
    alert_savings_below_forecast: Mapped[bool] = mapped_column(default=True, nullable=False)
    display_preferences_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceBudgetPlanRow(Base):
    __tablename__ = "finance_budget_plans"
    __table_args__ = (Index("ix_finance_budget_plans_active", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    style: Mapped[str] = mapped_column(String(32), nullable=False, default="custom")
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    debt_intensity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    cash_buffer_target_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discretionary_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_reserve_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    income_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    active_scope: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceBudgetPlanLineRow(Base):
    __tablename__ = "finance_budget_plan_lines"
    __table_args__ = (Index("ix_finance_budget_plan_lines_plan", "plan_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    source_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_custom: Mapped[bool] = mapped_column(default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subcategory: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    basis_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confidence: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    insufficient_data: Mapped[bool] = mapped_column(default=False, nullable=False)


class SettingsWatchChangeRow(Base):
    """Read-only detection of inverter settings changes (external or app)."""

    __tablename__ = "settings_watch_changes"
    __table_args__ = (Index("ix_settings_watch_changes_timestamp", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    changes_json: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="poll")
    note: Mapped[str] = mapped_column(String(256), nullable=False, default="")


class FinanceTransactionRow(Base):
    __tablename__ = "finance_transactions"
    __table_args__ = (
        Index("ix_finance_transactions_posted", "posted_on"),
        Index("ix_finance_transactions_fingerprint", "fingerprint"),
        Index("ix_finance_transactions_account", "account_id"),
        Index("ix_finance_transactions_active_posted", "is_deleted", "posted_on"),
        UniqueConstraint("fingerprint", name="uq_finance_transactions_fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    account_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    posted_on: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_pence: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    txn_type: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    subcategory: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    category_confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    transfer_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    excluded_from_budget: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    import_batch_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    is_transfer: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="GBP")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceImportBatchRow(Base):
    __tablename__ = "finance_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="preview")
    detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    money_in_pence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    money_out_pence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    date_from: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    date_to: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    rejects_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class FinanceChangeAuditRow(Base):
    __tablename__ = "finance_change_audit"
    __table_args__ = (Index("ix_finance_change_audit_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    new_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceBackupSnapshotRow(Base):
    __tablename__ = "finance_backup_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    location: Mapped[str] = mapped_column(String(16), nullable=False, default="local")
    web_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    account_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="")


class FinanceSinkingFundRow(Base):
    __tablename__ = "finance_sinking_funds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    saved_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    due_on: Mapped[str] = mapped_column(String(10), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceRecurringRuleRow(Base):
    __tablename__ = "finance_recurring_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    amount_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    cadence: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceHealthEventRow(Base):
    __tablename__ = "finance_health_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    repaired: Mapped[bool] = mapped_column(default=False, nullable=False)
    needs_review: Mapped[bool] = mapped_column(default=False, nullable=False)
