export const FEATURE_DEFINITIONS = [
  { key: "laser_power_w", label: "Laser power", unit: "W", decimals: 0 },
  { key: "welding_speed_mm_s", label: "Welding speed", unit: "mm/s", decimals: 1 },
  { key: "focal_position_error_mm", label: "Focal error", unit: "mm", decimals: 3 },
  { key: "shielding_gas_flow_l_min", label: "Shielding gas", unit: "L/min", decimals: 1 },
  { key: "melt_pool_temp_c", label: "Melt-pool temp.", unit: "°C", decimals: 0 },
  { key: "back_reflection_intensity", label: "Back reflection", unit: "norm.", decimals: 2 },
  { key: "plume_intensity", label: "Plume intensity", unit: "norm.", decimals: 2 },
  { key: "spatter_count", label: "Spatter count", unit: "count", decimals: 0 },
  { key: "vibration_rms", label: "Vibration RMS", unit: "mm/s", decimals: 3 },
  { key: "robot_path_error_mm", label: "Robot path error", unit: "mm", decimals: 3 },
  { key: "bead_width_mm", label: "Bead width", unit: "mm", decimals: 2 },
  { key: "bead_height_mm", label: "Bead height", unit: "mm", decimals: 2 },
  { key: "porosity_risk", label: "Porosity risk", unit: "norm.", decimals: 2 },
  { key: "visual_defect_score", label: "Visual defect", unit: "score", decimals: 1 },
  { key: "lens_contamination_level", label: "Lens contamination", unit: "norm.", decimals: 2 },
  { key: "cooling_system_alarm", label: "Cooling alarm", unit: "bool", decimals: 0 },
  { key: "time_since_lens_cleaning_h", label: "Since lens cleaning", unit: "h", decimals: 1 },
] as const;

export type FeatureKey = (typeof FEATURE_DEFINITIONS)[number]["key"];
export interface TelemetryPayload {
  [key: string]: unknown;
  device_id?: string;
  station_id?: string;
  timestamp?: string;
  sequence?: number;
  scenario?: string;
  features?: Record<string, number>;
}

export type TelemetryFeatures = Record<FeatureKey, number>;

export interface InferenceResult {
  predictedUrgency: number;
  adjustedUrgency: number;
  uncertainty: number;
  processInstability: number;
  label: "low" | "medium" | "high";
  recommendation: "do_nothing" | "inspect" | "minor_maintenance" | "major_maintenance" | "urgent_intervention";
  humanReview: boolean;
  humanOverride: boolean;
  modelName: string;
  modelVersion: string;
  qualityFlags: string[];
}

export interface TelemetryRecord {
  id: string;
  timestamp: string;
  receivedAt: string;
  stationId: string;
  deviceId: string;
  scenario: string;
  source: "mqtt" | "demo";
  features: TelemetryFeatures;
  inference: InferenceResult;
}

export interface DashboardState {
  connection: "demo" | "connecting" | "mqtt" | "degraded";
  brokerUrl: string;
  mqttTopic: string;
  station: {
    id: string;
    location: string;
    line: string;
    asset: string;
  };
  model: {
    name: string;
    version: string;
    source: "python" | "fallback";
  };
  current: TelemetryRecord | null;
  history: TelemetryRecord[];
  alerts: Array<{
    id: string;
    timestamp: string;
    title: string;
    detail: string;
    level: "info" | "warning" | "critical";
  }>;
  totals: {
    messages: number;
    reviews: number;
    overrides: number;
    mqttMessages: number;
  };
  updatedAt: string;
}
