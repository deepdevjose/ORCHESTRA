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
 * Deterministic fleet used when no MQTT broker is configured. It is intentionally
 * labelled as synthetic in the UI: it exercises the complete data contract and
 * the human-review workflow, but is not evidence from a production cell.
 */
export const DEMO_MACHINE_PROFILES: DemoMachineProfile[] = [
  { deviceId: "esp32-wroom32-laser-01", stationId: "CN-SUZHOU-LW-01", name: "Cell 01 · Orion", location: "Suzhou · Jiangsu", line: "Battery enclosure A", asset: "SIASUN SR12A", scenarioOffset: 0, riskBias: 0.00 },
  { deviceId: "esp32-sim-02", stationId: "CN-SUZHOU-LW-02", name: "Cell 02 · Vega", location: "Suzhou · Jiangsu", line: "Battery enclosure A", asset: "SIASUN SR12A", scenarioOffset: 1, riskBias: 0.08 },
  { deviceId: "esp32-sim-03", stationId: "CN-SUZHOU-LW-03", name: "Cell 03 · Altair", location: "Suzhou · Jiangsu", line: "Battery enclosure B", asset: "SIASUN SR12A", scenarioOffset: 2, riskBias: 0.16 },
  { deviceId: "esp32-sim-04", stationId: "CN-SHANGHAI-LW-04", name: "Cell 04 · Polaris", location: "Shanghai · Pudong", line: "Battery enclosure B", asset: "SIASUN SR12A", scenarioOffset: 3, riskBias: 0.22 },
  { deviceId: "esp32-sim-05", stationId: "CN-WUXI-LW-05", name: "Cell 05 · Sirius", location: "Wuxi · Jiangsu", line: "Thermal shield C", asset: "SIASUN SR12A", scenarioOffset: 4, riskBias: 0.04 },
  { deviceId: "esp32-sim-06", stationId: "CN-WUXI-LW-06", name: "Cell 06 · Lyra", location: "Wuxi · Jiangsu", line: "Thermal shield C", asset: "SIASUN SR12A", scenarioOffset: 5, riskBias: 0.12 },
  { deviceId: "esp32-sim-07", stationId: "KR-SEOUL-LW-07", name: "Cell 07 · Hanul", location: "Seoul · Gyeonggi", line: "Structural seam D", asset: "SIASUN SR12A", scenarioOffset: 0, riskBias: 0.18 },
  { deviceId: "esp32-sim-08", stationId: "KR-SEOUL-LW-08", name: "Cell 08 · Nuri", location: "Seoul · Gyeonggi", line: "Structural seam D", asset: "SIASUN SR12A", scenarioOffset: 2, riskBias: 0.28 },
  { deviceId: "esp32-sim-09", stationId: "CN-SUZHOU-LW-09", name: "Cell 09 · Jade", location: "Suzhou · Jiangsu", line: "Final inspection E", asset: "SIASUN SR12A", scenarioOffset: 4, riskBias: 0.34 },
  { deviceId: "esp32-sim-10", stationId: "CN-SHANGHAI-LW-10", name: "Cell 10 · Meridian", location: "Shanghai · Pudong", line: "Final inspection E", asset: "SIASUN SR12A", scenarioOffset: 1, riskBias: 0.42 },
];

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

export function createDemoTelemetry(sequence: number, machineIndex = 0): TelemetryPayload {
  const profile = DEMO_MACHINE_PROFILES[machineIndex % DEMO_MACHINE_PROFILES.length];
  const phase = sequence / 3.5 + machineIndex * 0.37;
  const scenario = scenarioNames[(Math.floor(sequence / 5) + profile.scenarioOffset) % scenarioNames.length];
  const drift = scenario === "normal" ? profile.riskBias * 0.25 : Math.min(1, (sequence % 5) / 4 + profile.riskBias * 0.35);
  const risk = profile.riskBias;
  const features: Record<string, number> = {
    laser_power_w: 1800 + wave(phase, 0.6, 45) + (scenario === "high_laser_power" ? 290 * drift : 55 * risk),
    welding_speed_mm_s: 35 + wave(phase, 0.45, 1.7) + (scenario === "fixture_vibration" ? -2 * risk : 0),
    focal_position_error_mm: 0.08 + Math.abs(wave(phase, 0.55, 0.04)) + (scenario === "focal_offset" ? 0.28 * drift : 0.04 * risk),
    shielding_gas_flow_l_min: 18 + wave(phase, 0.3, 0.6) - (scenario === "low_shielding_gas" ? 6 * drift : 0.5 * risk),
    melt_pool_temp_c: 1450 + wave(phase, 0.35, 48) + (scenario === "high_laser_power" ? 150 * drift : 35 * risk),
    back_reflection_intensity: 0.34 + wave(phase, 0.42, 0.035) + (scenario === "lens_contamination_proxy" ? 0.24 * drift : 0.04 * risk),
    plume_intensity: 0.45 + wave(phase, 0.37, 0.04) + (scenario === "lens_contamination_proxy" ? 0.13 * drift : 0.025 * risk),
    spatter_count: 3 + Math.max(0, Math.round(wave(phase, 0.7, 2))) + (scenario === "high_laser_power" ? 5 * drift : Math.round(2 * risk)),
    vibration_rms: 0.08 + Math.abs(wave(phase, 0.52, 0.018)) + (scenario === "fixture_vibration" ? 0.19 * drift : 0.03 * risk),
    robot_path_error_mm: 0.05 + Math.abs(wave(phase, 0.41, 0.015)) + (scenario === "fixture_vibration" ? 0.13 * drift : 0.025 * risk),
    bead_width_mm: 2 + wave(phase, 0.5, 0.06) + (scenario === "focal_offset" ? 0.18 * drift : 0.025 * risk),
    bead_height_mm: 0.62 + wave(phase, 0.33, 0.025) + 0.02 * risk,
    porosity_risk: 0.12 + Math.abs(wave(phase, 0.28, 0.025)) + (scenario === "low_shielding_gas" ? 0.35 * drift : 0.12 * risk),
    visual_defect_score: 8 + Math.max(0, wave(phase, 0.27, 3)) + (scenario === "focal_offset" ? 18 * drift : 12 * risk),
    lens_contamination_level: 0.12 + Math.abs(wave(phase, 0.24, 0.025)) + (scenario === "lens_contamination_proxy" ? 0.42 * drift : 0.18 * risk),
    cooling_system_alarm: sequence % (17 - Math.min(6, Math.round(risk * 10))) === 0 ? 1 : 0,
    time_since_lens_cleaning_h: 24 + (sequence % 12) * 1.7 + (scenario === "lens_contamination_proxy" ? 22 * drift : 18 * risk),
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
    features,
    ...features,
  };
}
