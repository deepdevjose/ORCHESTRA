import { getLiveTelemetryService } from "../../../lib/live-service";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SCENARIOS = ["normal", "low_shielding_gas", "lens_contamination", "focal_offset", "fixture_vibration", "high_laser_power"];

export async function POST(request: Request) {
  try {
    const body = await request.json() as { deviceId?: string; scenario?: string };
    if (!body.deviceId || !body.scenario || !SCENARIOS.includes(body.scenario)) {
      return Response.json({ ok: false, error: "deviceId and a valid scenario are required." }, { status: 400 });
    }
    const state = getLiveTelemetryService().publishScenario(body.deviceId, body.scenario);
    return Response.json({ ok: true, state }, { headers: { "cache-control": "no-store" } });
  } catch (error) {
    return Response.json({ ok: false, error: error instanceof Error ? error.message : "Unable to publish scenario." }, { status: 422 });
  }
}