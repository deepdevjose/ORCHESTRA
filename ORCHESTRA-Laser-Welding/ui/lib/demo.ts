import { FEATURE_DEFINITIONS, TelemetryPayload } from "./types";

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

export function createDemoTelemetry(sequence: number): TelemetryPayload {
  const phase = sequence / 3.5;
  const scenario = scenarioNames[Math.floor(sequence / 5) % scenarioNames.length];
  const drift = scenario === "normal" ? 0 : Math.min(1, (sequence % 5) / 4);
  const features: Record<string, number> = {
    laser_power_w: 1800 + wave(phase, 0.6, 45) + (scenario === "high_laser_power" ? 290 * drift : 0),
    welding_speed_mm_s: 35 + wave(phase, 0.45, 1.7) + (scenario === "speed_variation" ? 8 * drift : 0),
    focal_position_error_mm: 0.08 + Math.abs(wave(phase, 0.55, 0.04)) + (scenario === "focal_offset" ? 0.28 * drift : 0),
    shielding_gas_flow_l_min: 18 + wave(phase, 0.3, 0.6) - (scenario === "low_shielding_gas" ? 6 * drift : 0),
    melt_pool_temp_c: 1450 + wave(phase, 0.35, 48) + (scenario === "high_laser_power" ? 150 * drift : 0),
    back_reflection_intensity: 0.34 + wave(phase, 0.42, 0.035) + (scenario === "lens_contamination_proxy" ? 0.24 * drift : 0),
    plume_intensity: 0.45 + wave(phase, 0.37, 0.04) + (scenario === "lens_contamination_proxy" ? 0.13 * drift : 0),
    spatter_count: 3 + Math.max(0, Math.round(wave(phase, 0.7, 2))) + (scenario === "high_laser_power" ? 5 * drift : 0),
    vibration_rms: 0.08 + Math.abs(wave(phase, 0.52, 0.018)) + (scenario === "fixture_vibration" ? 0.19 * drift : 0),
    robot_path_error_mm: 0.05 + Math.abs(wave(phase, 0.41, 0.015)) + (scenario === "fixture_vibration" ? 0.13 * drift : 0),
    bead_width_mm: 2 + wave(phase, 0.5, 0.06) + (scenario === "focal_offset" ? 0.18 * drift : 0),
    bead_height_mm: 0.62 + wave(phase, 0.33, 0.025),
    porosity_risk: 0.12 + Math.abs(wave(phase, 0.28, 0.025)) + (scenario === "low_shielding_gas" ? 0.35 * drift : 0),
    visual_defect_score: 8 + Math.max(0, wave(phase, 0.27, 3)) + (scenario === "focal_offset" ? 18 * drift : 0),
    lens_contamination_level: 0.12 + Math.abs(wave(phase, 0.24, 0.025)) + (scenario === "lens_contamination_proxy" ? 0.42 * drift : 0),
    cooling_system_alarm: sequence % 17 === 0 ? 1 : 0,
    time_since_lens_cleaning_h: 24 + (sequence % 12) * 1.7 + (scenario === "lens_contamination_proxy" ? 22 * drift : 0),
  };

  for (const definition of FEATURE_DEFINITIONS) {
    const value = features[definition.key];
    features[definition.key] = Number.isFinite(value) ? value : 0;
  }

  return {
    device_id: "esp32-demo-01",
    station_id: "CN-SUZHOU-LW-01",
    timestamp: new Date().toISOString(),
    sequence,
    scenario,
    features,
    ...features,
  };
}
