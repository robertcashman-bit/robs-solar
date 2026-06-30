from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
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
