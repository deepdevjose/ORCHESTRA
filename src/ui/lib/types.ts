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
  machine_name?: string;
  line?: string;
  location?: string;
  features?: Record<string, number>;
  shift_id?: string;
  shift_load_pieces?: number;
  pieces_produced?: number;
  pieces_remaining?: number;
  order_id?: string;
  order_target_pieces?: number;
  checkpoint_pieces?: number;
  maintenance_count?: number;
  service_wear?: number;
  lifetime_percent?: number;
  simulated_health?: number;
  simulated_risk?: number;
  data_quality?: "valid" | "atypical";
  operational_state?: MachineOperationalState;
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

export type MachineOperationalState = "production" | "inspection" | "maintenance_planned" | "maintenance_hold" | "stopped";
export type DecisionAction = "acknowledge" | "inspect" | "hold_production" | "schedule_minor_maintenance" | "schedule_major_maintenance" | "urgent_intervention" | "resume_production" | "reset_lifetime";

export type AgentKey = "telemetry_quality" | "predictive_inference" | "shift_scheduler";

export interface AgentDecisionTrace {
  agent: AgentKey;
  label: string;
  status: "pass" | "review" | "hold";
  decision: string;
  detail: string;
  timestamp: string;
}

export interface ProductionOrder {
  id: string;
  productType: string;
  targetPieces: number;
  completedPieces: number;
  remainingPieces: number;
  shiftId: string;
  shiftLengthMinutes: number;
  checkpointEveryPieces: number;
  lastCheckpointPieces: number;
  nextCheckpointPieces: number;
  fleetPiecesPerSecond: number;
  cycleTimeSecondsPerCell: number;
  simulationSecondsPerTick: number;
  status: "setup" | "running" | "paused" | "completed";
  assumption: string;
}

export interface FleetMachine {
  deviceId: string;
  stationId: string;
  name: string;
  location: string;
  line: string;
  asset: string;
  operationalState: MachineOperationalState;
  source: "mqtt" | "demo";
  scenario: string;
  lastSeen: string;
  current: TelemetryRecord | null;
  urgency: number;
  uncertainty: number;
  label: InferenceResult["label"];
  recommendation: InferenceResult["recommendation"];
  humanReview: boolean;
  trend: number[];
  shiftId: string;
  shiftLoadPieces: number;
  piecesProduced: number;
  piecesRemaining: number;
  health: number;
  lifetimePercent: number;
  maintenanceCount: number;
  serviceWear: number;
  dataQuality: "valid" | "atypical";
  agentTrace: AgentDecisionTrace[];
  productionPlan: {
    maxAdditionalPieces: number;
    reevaluateEveryPieces: number;
    action: "continue" | "reduce_load" | "stop_and_review";
  };
}

export interface DecisionRecord {
  id: string;
  timestamp: string;
  deviceId: string;
  machineName: string;
  action: DecisionAction;
  operator: string;
  note: string;
  transport: "mqtt" | "simulated";
  status: "accepted" | "published";
}

export interface ModelTelemetry {
  framesPerMinute: number;
  averageUrgency: number;
  averageUncertainty: number;
  highRiskMachines: number;
  reviewQueue: number;
  modelEvents: Array<{
    id: string;
    timestamp: string;
    deviceId: string;
    event: string;
    detail: string;
    level: "info" | "warning" | "critical";
  }>;
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
  fleet: FleetMachine[];
  selectedDeviceId: string;
  decisions: DecisionRecord[];
  modelTelemetry: ModelTelemetry;
  simulation: {
    enabled: boolean;
    machineCount: number;
    label: string;
    failureHorizonMinutes: number;
    productionOrder: ProductionOrder | null;
    checkpointCount: number;
    lastCheckpointAt: string | null;
    cycleTimeSecondsPerCell: number;
    fleetPiecesPerSecond: number;
    simulationSecondsPerTick: number;
  };
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
