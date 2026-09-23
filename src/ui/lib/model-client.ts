import { FEATURE_DEFINITIONS, InferenceResult, TelemetryFeatures, TelemetryPayload } from "./types";

function clamp(value: number, low: number, high: number) {
  return Math.min(high, Math.max(low, value));
}

/** Apply the documented local fallback when the Python inference service is unavailable. */
export function fallbackInference(features: TelemetryFeatures): InferenceResult {
  const powerRisk = clamp(Math.abs(features.laser_power_w - 1800) / 360, 0, 1);
  const temperatureRisk = clamp(Math.abs(features.melt_pool_temp_c - 1450) / 260, 0, 1);
  const focalRisk = clamp(features.focal_position_error_mm / 0.45, 0, 1);
  const gasRisk = clamp((18 - features.shielding_gas_flow_l_min) / 8, 0, 1);
  const opticalRisk = clamp((features.back_reflection_intensity + features.plume_intensity) / 1.6, 0, 1);
  const motionRisk = clamp(features.vibration_rms / 0.32, 0, 1);
  const qualityRisk = clamp(features.porosity_risk * 0.65 + features.visual_defect_score / 100 * 0.35, 0, 1);
  const maintenanceRisk = clamp(features.lens_contamination_level * 0.7 + features.time_since_lens_cleaning_h / 90 * 0.3, 0, 1);
  const raw = 0.12 * temperatureRisk + 0.1 * powerRisk + 0.13 * focalRisk + 0.1 * gasRisk + 0.14 * opticalRisk + 0.12 * motionRisk + 0.17 * qualityRisk + 0.12 * maintenanceRisk + 0.08 * features.cooling_system_alarm;
  const predictedUrgency = clamp(raw * 100, 0, 100);
  const uncertainty = clamp(0.2 + qualityRisk * 0.28 + features.cooling_system_alarm * 0.25 + (Math.abs(predictedUrgency - 55) < 12 ? 0.25 : 0.05), 0, 1);
  const humanReview = uncertainty >= 0.45 || predictedUrgency >= 70;
  const adjustedUrgency = humanReview ? clamp(predictedUrgency + (predictedUrgency >= 70 ? 2 : 0), 0, 100) : predictedUrgency;
  const label = adjustedUrgency > 70 ? "high" : adjustedUrgency > 40 ? "medium" : "low";
  const recommendation = adjustedUrgency >= 82 ? "urgent_intervention" : adjustedUrgency >= 65 ? "major_maintenance" : adjustedUrgency >= 45 || humanReview ? "inspect" : "do_nothing";
  const qualityFlags: string[] = [];
  if (features.cooling_system_alarm > 0.5) qualityFlags.push("Cooling alarm");
  if (gasRisk > 0.55) qualityFlags.push("Low shielding gas");
  if (maintenanceRisk > 0.6) qualityFlags.push("Optical maintenance drift");

  return {
    predictedUrgency,
    adjustedUrgency,
    uncertainty,
    processInstability: predictedUrgency,
    label,
    recommendation,
    humanReview,
    humanOverride: false,
    modelName: "fallback_rule",
    modelVersion: "ui-v0.1",
    qualityFlags,
  };
}

function extractFeatures(payload: TelemetryPayload): TelemetryFeatures {
  const nested = payload.features ?? {};
  return Object.fromEntries(
    FEATURE_DEFINITIONS.map(({ key }) => [key, Number(nested[key] ?? payload[key])]),
  ) as TelemetryFeatures;
}

/** Send one frame to the Python model service and fall back locally on transport failure. */
export async function scoreTelemetry(payload: TelemetryPayload): Promise<InferenceResult> {
  const features = extractFeatures(payload);
  const endpoint = process.env.ORCHESTRA_MODEL_URL ?? "http://127.0.0.1:8787/score";
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...payload, features }),
      signal: AbortSignal.timeout(1800),
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Model service returned " + response.status);
    return (await response.json()) as InferenceResult;
  } catch {
    return fallbackInference(features);
  }
}
