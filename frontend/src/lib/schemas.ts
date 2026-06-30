import { z } from "zod";

export const userRoleSchema = z.enum(["admin", "viewer"]);

export const liveMetricsSchema = z.object({
  pv_power_w: z.number(),
  battery_soc_pct: z.number(),
  battery_power_w: z.number().nullable().optional(),
  house_load_w: z.number(),
  grid_import_w: z.number(),
  grid_export_w: z.number(),
  inverter_mode: z.string(),
  inverter_status: z.string(),
  daily_pv_kwh: z.number(),
  daily_import_kwh: z.number(),
  daily_export_kwh: z.number(),
  timestamp: z.string(),
  pv1_power_w: z.number().nullable().optional(),
  pv2_power_w: z.number().nullable().optional(),
  battery_voltage_v: z.number().nullable().optional(),
  battery_current_a: z.number().nullable().optional(),
  battery_temp_c: z.number().nullable().optional(),
  battery_soh_pct: z.number().nullable().optional(),
  grid_voltage_v: z.number().nullable().optional(),
  grid_frequency_hz: z.number().nullable().optional(),
  daily_battery_charge_kwh: z.number().nullable().optional(),
  daily_battery_discharge_kwh: z.number().nullable().optional(),
  system_work_mode: z.string().nullable().optional(),
});

export const connectivitySchema = z.object({
  backend_healthy: z.boolean(),
  adapter_mode: z.string(),
  adapter_connected: z.boolean(),
  last_successful_poll: z.string().nullable().optional(),
  degraded_reason: z.string().nullable().optional(),
});

export const userInfoSchema = z.object({
  username: z.string(),
  role: userRoleSchema,
});

export const loginResponseSchema = z.object({
  user: userInfoSchema,
  csrf_token: z.string(),
});

export const sessionResponseSchema = z.object({
  user: userInfoSchema,
  csrf_token: z.string(),
});

export const healthResponseSchema = z.object({
  status: z.string(),
  adapter_mode: z.string(),
  read_only: z.boolean(),
  timestamp: z.string(),
});

export const auditEntrySchema = z.object({
  id: z.number(),
  timestamp: z.string(),
  username: z.string(),
  role: userRoleSchema,
  action: z.string(),
  request_payload: z.record(z.string(), z.unknown()),
  validation_result: z.string(),
  adapter_response: z.string().nullable().optional(),
  outcome: z.string(),
});

export const auditListSchema = z.object({
  entries: z.array(auditEntrySchema),
  total: z.number(),
});

export const exportLimitSchema = z.object({
  limit_w: z
    .number()
    .min(0)
    .max(8000)
    .refine((value) => value % 100 === 0, {
      message: "Export limit must be a multiple of 100W",
    }),
});

export const controlWriteResultSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  audit_id: z.number(),
  applied_value: z.record(z.string(), z.unknown()).optional().nullable(),
  verified: z.boolean().optional(),
  verification_pending: z.boolean().optional(),
  verification_message: z.string().optional(),
});

export const operatingModeSchema = z.object({
  mode: z.enum(["self_use", "backup", "feed_in", "off_grid"]),
});

export const scheduleWindowSchema = z
  .object({
    start: z.string().regex(/^\d{2}:\d{2}$/, "Start time must be HH:MM"),
    end: z.string().regex(/^\d{2}:\d{2}$/, "End time must be HH:MM"),
    action: z.enum(["charge", "discharge", "idle"]),
    power_w: z.number().min(0).max(8000).optional(),
    target_soc_pct: z.number().min(0).max(100).optional(),
    grid_charge_enabled: z.boolean().optional(),
  })
  .superRefine((value, ctx) => {
    for (const field of ["start", "end"] as const) {
      const [hourText, minuteText] = value[field].split(":");
      const hour = Number(hourText);
      const minute = Number(minuteText);
      if (hour > 23 || minute > 59) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${field === "start" ? "Start" : "End"} time must be a valid HH:MM value`,
          path: [field],
        });
      }
    }
  });

export const scheduleSchema = z.object({
  windows: z.array(scheduleWindowSchema).min(1).max(24),
});

export const touBandWriteSchema = z.object({
  slot: z.number().min(1).max(6),
  start: z.string().regex(/^\d{2}:\d{2}$/, "Start time must be HH:MM"),
  target_soc_pct: z.number().min(0).max(100).optional(),
  grid_charge_enabled: z.boolean(),
  power_w: z.number().min(0).max(10000).optional(),
});

export const touBandsRequestSchema = z.object({
  bands: z.array(touBandWriteSchema).min(1).max(6),
});

export type TouBandWrite = z.infer<typeof touBandWriteSchema>;

export const restoreResultSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  audit_id: z.number(),
  restored_snapshot_id: z.number().nullable().optional(),
});

export const adapterCapabilitiesSchema = z.object({
  mode: z.string(),
  supports_read: z.boolean(),
  supports_write: z.boolean(),
  supported_writes: z.array(z.string()),
  notes: z.array(z.string()).optional(),
});

export const capabilitiesResponseSchema = z.object({
  adapter: adapterCapabilitiesSchema,
  data_source: z.string(),
  read_only: z.boolean(),
  enable_live_writes: z.boolean(),
  sunsynk_enable_unverified_writes: z.boolean(),
  plant_id: z.string().nullable().optional(),
  plant_name: z.string().nullable().optional(),
  modbus_host: z.string().nullable().optional(),
  modbus_port: z.number().nullable().optional(),
  modbus_slave_id: z.number().nullable().optional(),
  poll_interval_live_seconds: z.number().nullable().optional(),
  poll_interval_energy_seconds: z.number().nullable().optional(),
  octopus_configured: z.boolean().optional(),
});

export type LiveMetrics = z.infer<typeof liveMetricsSchema>;
export type ConnectivityStatus = z.infer<typeof connectivitySchema>;
export type UserInfo = z.infer<typeof userInfoSchema>;
export type AuditEntry = z.infer<typeof auditEntrySchema>;
export type CapabilitiesResponse = z.infer<typeof capabilitiesResponseSchema>;

export const historyRangeSchema = z.enum(["day", "week", "month"]);

export const metricHistoryPointSchema = z.object({
  timestamp: z.string(),
  pv_power_w: z.number(),
  battery_soc_pct: z.number(),
  house_load_w: z.number(),
  grid_import_w: z.number(),
  grid_export_w: z.number(),
  battery_soh_pct: z.number().nullable().optional(),
});

export const metricHistorySchema = z.object({
  range: historyRangeSchema,
  points: z.array(metricHistoryPointSchema),
});

export const metricSummarySchema = z.object({
  range: historyRangeSchema,
  pv_kwh: z.number(),
  consumption_kwh: z.number(),
  import_kwh: z.number(),
  export_kwh: z.number(),
  self_consumption_pct: z.number(),
  import_cost: z.number(),
  export_credit: z.number(),
  net_cost: z.number(),
  estimated_cost_without_solar: z.number(),
  savings: z.number(),
  currency: z.string(),
});

export const metricCompareDeltaSchema = z.object({
  label: z.string(),
  today: z.number(),
  yesterday: z.number(),
  unit: z.string(),
  higher_is_better: z.boolean(),
});

export const metricCompareSchema = z.object({
  today: metricSummarySchema,
  yesterday: metricSummarySchema,
  deltas: z.array(metricCompareDeltaSchema),
});

export type MetricCompare = z.infer<typeof metricCompareSchema>;

export const tariffSettingsSchema = z.object({
  import_rate: z.number().min(0).max(10),
  export_rate: z.number().min(0).max(10),
  currency: z.string().length(3),
});

export const touBandSchema = z.object({
  slot: z.number(),
  start: z.string(),
  end: z.string(),
  target_soc_pct: z.number().nullable().optional(),
  grid_charge_enabled: z.boolean(),
  power_w: z.number().nullable().optional(),
});

export const inverterSettingsSchema = z.object({
  inverter_sn: z.string(),
  plant_id: z.string(),
  plant_name: z.string(),
  plant_permissions: z.array(z.string()),
  write_allowed: z.boolean(),
  write_denied_reason: z.string(),
  sys_work_mode: z.string(),
  sys_work_mode_label: z.string(),
  energy_mode: z.string(),
  solar_sell: z.boolean(),
  export_limit_mode: z.string(),
  discharge_current_a: z.number().nullable().optional(),
  bands: z.array(touBandSchema),
  active_band_slot: z.number().nullable().optional(),
  active_band: touBandSchema.nullable().optional(),
  diagnosis: z.string(),
});

export type InverterSettings = z.infer<typeof inverterSettingsSchema>;
export type TouBand = z.infer<typeof touBandSchema>;

export const octopusConfigStatusSchema = z.object({
  api_key_set: z.boolean(),
  account_number: z.string(),
  mpan: z.string(),
  meter_serial: z.string(),
  region: z.string(),
  configured: z.boolean(),
});

export const octopusDiscoverResultSchema = z.object({
  account_number: z.string(),
  mpan: z.string(),
  meter_serial: z.string(),
  region: z.string(),
  import_tariff_code: z.string().optional(),
});

export const octopusTariffSchema = z.object({
  import_tariff_code: z.string(),
  import_product_code: z.string(),
  import_display_name: z.string(),
  import_rate_pence: z.number().nullable().optional(),
  export_tariff_code: z.string(),
  export_product_code: z.string(),
  export_display_name: z.string(),
  export_rate_pence: z.number().nullable().optional(),
  standing_charge_pence: z.number().nullable().optional(),
  is_variable: z.boolean(),
  tariff_family: z.string(),
  region: z.string(),
});

export type OctopusConfigStatus = z.infer<typeof octopusConfigStatusSchema>;
export type OctopusDiscoverResult = z.infer<typeof octopusDiscoverResultSchema>;
export type OctopusTariff = z.infer<typeof octopusTariffSchema>;

export const dispatchWindowSchema = z.object({
  start: z.string(),
  end: z.string(),
  source: z.string(),
  delta_kwh: z.number().nullable().optional(),
});

export const offPeakWindowSchema = z.object({
  start: z.string(),
  end: z.string(),
});

export const dispatchResponseSchema = z.object({
  off_peak_window: offPeakWindowSchema,
  planned: z.array(dispatchWindowSchema),
  completed: z.array(dispatchWindowSchema),
  tariff_family: z.string(),
});

export type DispatchResponse = z.infer<typeof dispatchResponseSchema>;

export const autoScheduleStatusSchema = z.object({
  enabled: z.boolean(),
  soc_floor_pct: z.number(),
  last_run_at: z.string().nullable().optional(),
  last_run_message: z.string(),
  last_write_audit_id: z.number().nullable().optional(),
  next_cheap_windows: z.array(dispatchWindowSchema),
  computed_bands: z.array(touBandWriteSchema),
});

export type AutoScheduleStatus = z.infer<typeof autoScheduleStatusSchema>;

export const reconciliationIntervalSchema = z.object({
  start: z.string(),
  end: z.string(),
  consumption_kwh: z.number(),
  is_cheap: z.boolean(),
});

export const reconciliationSchema = z.object({
  range: historyRangeSchema,
  meter_import_kwh: z.number(),
  cheap_import_kwh: z.number(),
  day_import_kwh: z.number(),
  export_kwh: z.number(),
  import_cost_gbp: z.number(),
  export_earnings_gbp: z.number(),
  net_bill_impact_gbp: z.number(),
  inverter_estimate_gbp: z.number(),
  delta_gbp: z.number(),
  currency: z.string(),
  intervals: z.array(reconciliationIntervalSchema),
  configured: z.boolean(),
  message: z.string(),
});

export const notificationCategoryToggleSchema = z.object({
  soc_low: z.boolean(),
  soc_high: z.boolean(),
  import_high: z.boolean(),
  offline: z.boolean(),
  negative_price: z.boolean(),
  price_spike: z.boolean(),
  dispatch_available: z.boolean(),
  export_price_high: z.boolean(),
  soc_low_before_offpeak: z.boolean(),
  inverter_fault: z.boolean(),
});

export const notificationSettingsStatusSchema = z.object({
  webhook_url_set: z.boolean(),
  smtp_configured: z.boolean(),
  email_to: z.string(),
  export_price_threshold_pence: z.number(),
  categories: notificationCategoryToggleSchema,
});

export const notificationSettingsSchema = notificationSettingsStatusSchema.extend({
  webhook_url: z.string().optional(),
  smtp_host: z.string().optional(),
  smtp_port: z.number().optional(),
  smtp_user: z.string().optional(),
  smtp_password: z.string().optional(),
});

export const chargeWindowStatusSchema = z.object({
  importing_on_cheap_window: z.boolean(),
  active: z.boolean(),
  source: z.string().optional().default(""),
  window_start: z.string().optional().default(""),
  window_end: z.string().optional().default(""),
  grid_import_w: z.number().optional().default(0),
  battery_soc_pct: z.number().optional().default(0),
  message: z.string().optional().default(""),
});

export const sellOpportunitySchema = z.object({
  worth_selling: z.boolean(),
  battery_soc_pct: z.number().optional().default(0),
  export_rate_pence: z.number().nullable().optional(),
  import_rate_pence: z.number().nullable().optional(),
  threshold_pence: z.number().optional().default(0),
  sellable_kwh: z.number().optional().default(0),
  estimated_value_gbp: z.number().optional().default(0),
  recommended_mode: z.string().optional().default("feed_in"),
  headline: z.string().optional().default(""),
  message: z.string().optional().default(""),
  configured: z.boolean().optional().default(false),
});

export const evStatusSchema = z.object({
  car_charging_likely: z.boolean(),
  in_dispatch_window: z.boolean(),
  house_load_w: z.number(),
  message: z.string(),
});

export const automationRuleSchema = z.object({
  id: z.string(),
  name: z.string(),
  enabled: z.boolean(),
  condition: z.string(),
  condition_value: z.number(),
  condition_value_end: z.number().nullable().optional(),
  action: z.string(),
  action_value: z.boolean().nullable().optional(),
  cooldown_minutes: z.number(),
});

export const automationRulesResponseSchema = z.object({
  rules: z.array(automationRuleSchema),
});

export const safetySettingsSchema = z.object({
  read_only: z.boolean(),
  enable_live_writes: z.boolean(),
  runtime_overrides: z.boolean().optional(),
});

export const aiActionKindSchema = z.enum([
  "set_tou_bands",
  "set_export_limit",
  "set_operating_mode",
  "set_auto_schedule",
]);

export const aiProposedActionSchema = z.object({
  kind: aiActionKindSchema,
  endpoint: z.string(),
  summary: z.string(),
  reason: z.string(),
  body: z.record(z.string(), z.unknown()).default({}),
});

export const aiAssessmentSchema = z.object({
  optimal: z.boolean(),
  headline: z.string(),
  findings: z.array(z.string()).default([]),
  proposed_actions: z.array(aiProposedActionSchema).default([]),
});

export const aiStatusSchema = z.object({
  enabled: z.boolean(),
  model: z.string().optional().default(""),
  reason: z.string().optional().default(""),
});

export const aiChatResponseSchema = z.object({
  reply: z.string(),
  proposed_actions: z.array(aiProposedActionSchema).default([]),
});

export type Reconciliation = z.infer<typeof reconciliationSchema>;
export type NotificationSettingsStatus = z.infer<typeof notificationSettingsStatusSchema>;
export type EvStatus = z.infer<typeof evStatusSchema>;
export type ChargeWindowStatus = z.infer<typeof chargeWindowStatusSchema>;
export type SellOpportunity = z.infer<typeof sellOpportunitySchema>;
export type AutomationRule = z.infer<typeof automationRuleSchema>;
export type SafetySettings = z.infer<typeof safetySettingsSchema>;
export type AiProposedAction = z.infer<typeof aiProposedActionSchema>;
export type AiAssessment = z.infer<typeof aiAssessmentSchema>;
export type AiStatus = z.infer<typeof aiStatusSchema>;
export type AiChatResponse = z.infer<typeof aiChatResponseSchema>;

export type HistoryRange = z.infer<typeof historyRangeSchema>;
export type MetricHistory = z.infer<typeof metricHistorySchema>;
export type MetricSummary = z.infer<typeof metricSummarySchema>;
export type TariffSettings = z.infer<typeof tariffSettingsSchema>;
