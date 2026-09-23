import { getLiveTelemetryService } from "../../../lib/live-service";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Configure an order, reset the simulation, or update the failure horizon. */
export async function POST(request: Request) {
  try {
    const body = await request.json() as { action?: "configure_order" | "reset" | "set_horizon"; failureHorizonMinutes?: number; targetPieces?: number; productType?: string; shiftLengthMinutes?: number };
    const service = getLiveTelemetryService();
    if (body.action === "reset") {
      return Response.json({ ok: true, state: service.resetSimulation() }, { headers: { "cache-control": "no-store" } });
    }
    if (body.action === "configure_order") {
      if (!Number.isFinite(body.targetPieces) || Number(body.targetPieces) < 1) {
        return Response.json({ ok: false, error: "targetPieces must be a positive number." }, { status: 400 });
      }
      return Response.json({ ok: true, state: service.configureOrder(Number(body.targetPieces), body.productType, Number(body.shiftLengthMinutes ?? 480)) }, { headers: { "cache-control": "no-store" } });
    }
    if (!Number.isFinite(body.failureHorizonMinutes)) {
      return Response.json({ ok: false, error: "failureHorizonMinutes must be a number." }, { status: 400 });
    }
    const state = service.setFailureHorizon(Number(body.failureHorizonMinutes));
    return Response.json({ ok: true, state }, { headers: { "cache-control": "no-store" } });
  } catch (error) {
    return Response.json({ ok: false, error: error instanceof Error ? error.message : "Unable to update simulation." }, { status: 422 });
  }
}
