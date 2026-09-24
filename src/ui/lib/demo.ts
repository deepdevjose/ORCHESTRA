import { FEATURE_DEFINITIONS, TelemetryPayload } from "./types";

export interface DemoMachineProfile {
  deviceId: string;
  stationId: string;
  name: string;
  location: string;
  line: string;
  asset: string;
  scenarioOffset: number;
  riskBias: number;
}

/**
 * Deterministic six-cell fleet used when no MQTT broker is configured. Cell 01
 * is reserved for the ESP32/MQTT edge path; cells 02-06 are synthetic fallback
 * streams for the five remaining machines in the 3D simulation.
 */
export const DEMO_MACHINE_PROFILES: DemoMachineProfile[] = [
  { deviceId: "esp32-wroom32-laser-01", stationId: "CN-SUZHOU-LW-01", name: "Cell 01 · Orion", location: "Suzhou · Jiangsu", line: "Battery enclosure A", asset: "SIASUN SR12A", scenarioOffset: 0, riskBias: 0.00 },
  { deviceId: "esp32-sim-02", stationId: "CN-SUZHOU-LW-02", name: "Cell 02 · Vega", location: "Suzhou · Jiangsu", line: "Battery enclosure A", asset: "SIASUN SR12A", scenarioOffset: 1, riskBias: 0.08 },
  { deviceId: "esp32-sim-03", stationId: "CN-SUZHOU-LW-03", name: "Cell 03 · Altair", location: "Suzhou · Jiangsu", line: "Battery enclosure B", asset: "SIASUN SR12A", scenarioOffset: 2, riskBias: 0.16 },
  { deviceId: "esp32-sim-04", stationId: "CN-SHANGHAI-LW-04", name: "Cell 04 · Polaris", location: "Shanghai · Pudong", line: "Battery enclosure B", asset: "SIASUN SR12A", scenarioOffset: 3, riskBias: 0.22 },
  { deviceId: "esp32-sim-05", stationId: "CN-WUXI-LW-05", name: "Cell 05 · Sirius", location: "Wuxi · Jiangsu", line: "Thermal shield C", asset: "SIASUN SR12A", scenarioOffset: 4, riskBias: 0.04 },
  { deviceId: "esp32-sim-06", stationId: "CN-WUXI-LW-06", name: "Cell 06 · Lyra", location: "Wuxi · Jiangsu", line: "Thermal shield C", asset: "SIASUN SR12A", scenarioOffset: 5, riskBias: 0.12 },
];

export const EDGE_MACHINE_COUNT = 1;
export const TOTAL_MACHINE_COUNT = DEMO_MACHINE_PROFILES.length;
export const SYNTHETIC_MACHINE_COUNT = TOTAL_MACHINE_COUNT - EDGE_MACHINE_COUNT;

const scenarioNames = [
  "normal",
  "low_shielding_gas",
  "lens_contamination_proxy",
  "focal_offset",
  "fixture_vibration",
  "high_laser_power",
];

function wave(index: number, frequency: number, amplitude: number, offset = 0) {
  return offset + Math.sin(index * frequency) * amplitude;
}

/** Generate one deterministic synthetic telemetry frame for the selected cell. */
export function createDemoTelemetry(sequence: number, machineIndex = 0, runtime?: { health: number; serviceWear: number; maintenanceCount: number; shiftId: string; shiftLoadPieces: number; piecesProduced: number; piecesRemaining: number; cooldownTicks: number }): TelemetryPayload {
  const profile = DEMO_MACHINE_PROFILES[machineIndex % DEMO_MACHINE_PROFILES.length];
  const phase = sequence / 3.5 + machineIndex * 0.37;
  const health = runtime?.health ?? profile.riskBias;
  const scenario = health >= 0.72 ? scenarioNames[1 + ((sequence + profile.scenarioOffset) % (scenarioNames.length - 1))] : scenarioNames[(Math.floor(sequence / 5) + profile.scenarioOffset) % scenarioNames.length];
  const drift = Math.min(1, health + (scenario === "normal" ? profile.riskBias * 0.25 : 0.18));
  const risk = profile.riskBias;
  const recovery = runtime?.cooldownTicks ? Math.max(0, 1 - runtime.cooldownTicks / 14) : 0;
  const degradation = Math.max(0, drift - recovery * 0.85);
  const features: Record<string, number> = {
    laser_power_w: 1800 + wave(phase, 0.6, 45) + (scenario === "high_laser_power" ? 290 * drift : 55 * risk) + 170 * degradation,
    welding_speed_mm_s: 35 + wave(phase, 0.45, 1.7) - (scenario === "fixture_vibration" ? 2 * risk : 0) - 5 * degradation,
    focal_position_error_mm: 0.08 + Math.abs(wave(phase, 0.55, 0.04)) + (scenario === "focal_offset" ? 0.28 * drift : 0.04 * risk) + 0.34 * degradation,
    shielding_gas_flow_l_min: 18 + wave(phase, 0.3, 0.6) - (scenario === "low_shielding_gas" ? 6 * drift : 0.5 * risk) - 4.5 * degradation,
    melt_pool_temp_c: 1450 + wave(phase, 0.35, 48) + (scenario === "high_laser_power" ? 150 * drift : 35 * risk) + 180 * degradation,
    back_reflection_intensity: 0.34 + wave(phase, 0.42, 0.035) + (scenario === "lens_contamination_proxy" ? 0.24 * drift : 0.04 * risk) + 0.25 * degradation,
    plume_intensity: 0.45 + wave(phase, 0.37, 0.04) + (scenario === "lens_contamination_proxy" ? 0.13 * drift : 0.025 * risk) + 0.16 * degradation,
    spatter_count: 3 + Math.max(0, Math.round(wave(phase, 0.7, 2))) + (scenario === "high_laser_power" ? 5 * drift : Math.round(2 * risk)) + Math.round(12 * degradation),
    vibration_rms: 0.08 + Math.abs(wave(phase, 0.52, 0.018)) + (scenario === "fixture_vibration" ? 0.19 * drift : 0.03 * risk) + 0.24 * degradation,
    robot_path_error_mm: 0.05 + Math.abs(wave(phase, 0.41, 0.015)) + (scenario === "fixture_vibration" ? 0.13 * drift : 0.025 * risk) + 0.18 * degradation,
    bead_width_mm: 2 + wave(phase, 0.5, 0.06) + (scenario === "focal_offset" ? 0.18 * drift : 0.025 * risk) + 0.22 * degradation,
    bead_height_mm: 0.62 + wave(phase, 0.33, 0.025) + 0.02 * risk - 0.08 * degradation,
    porosity_risk: Math.min(1, 0.12 + Math.abs(wave(phase, 0.28, 0.025)) + (scenario === "low_shielding_gas" ? 0.35 * drift : 0.12 * risk) + 0.55 * degradation),
    visual_defect_score: 8 + Math.max(0, wave(phase, 0.27, 3)) + (scenario === "focal_offset" ? 18 * drift : 12 * risk) + 45 * degradation,
    lens_contamination_level: Math.min(1, 0.12 + Math.abs(wave(phase, 0.24, 0.025)) + (scenario === "lens_contamination_proxy" ? 0.42 * drift : 0.18 * risk) + 0.55 * degradation),
    cooling_system_alarm: sequence % Math.max(3, 17 - Math.min(12, Math.round((risk + degradation) * 12))) === 0 ? 1 : 0,
    time_since_lens_cleaning_h: 24 + (sequence % 12) * 1.7 + (scenario === "lens_contamination_proxy" ? 22 * drift : 18 * risk) + 35 * degradation,
  };

  for (const definition of FEATURE_DEFINITIONS) {
    const value = features[definition.key];
    features[definition.key] = Number.isFinite(value) ? value : 0;
  }

  return {
    device_id: profile.deviceId,
    station_id: profile.stationId,
    machine_name: profile.name,
    location: profile.location,
    line: profile.line,
    timestamp: new Date().toISOString(),
    sequence,
    scenario,
    shift_id: runtime?.shiftId ?? `shift-${Math.floor(sequence / 40) + 1}`,
    shift_load_pieces: runtime?.shiftLoadPieces ?? 10000,
    pieces_produced: runtime?.piecesProduced ?? 0,
    pieces_remaining: runtime?.piecesRemaining ?? 10000,
    maintenance_count: runtime?.maintenanceCount ?? 0,
    service_wear: runtime?.serviceWear ?? 0,
    lifetime_percent: 100 - (runtime?.serviceWear ?? 0) * 100,
    simulated_health: health,
    simulated_risk: degradation,
    data_quality: degradation >= 0.78 ? "atypical" : "valid",
    features,
    ...features,
  };
}
