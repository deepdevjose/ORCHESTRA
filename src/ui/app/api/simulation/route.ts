import { getLiveTelemetryService } from "../../../lib/live-service";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json() as { failureHorizonMinutes?: number };
    if (!Number.isFinite(body.failureHorizonMinutes)) {
      return Response.json({ ok: false, error: "failureHorizonMinutes must be a number." }, { status: 400 });
    }
    const state = getLiveTelemetryService().setFailureHorizon(Number(body.failureHorizonMinutes));
    return Response.json({ ok: true, state }, { headers: { "cache-control": "no-store" } });
  } catch (error) {
    return Response.json({ ok: false, error: error instanceof Error ? error.message : "Unable to update simulation." }, { status: 422 });
  }
}