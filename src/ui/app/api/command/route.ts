import { getLiveTelemetryService } from "../../../lib/live-service";
import { DecisionAction } from "../../../lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ACTIONS: DecisionAction[] = [
  "acknowledge",
  "inspect",
  "hold_production",
  "schedule_minor_maintenance",
  "schedule_major_maintenance",
  "urgent_intervention",
  "resume_production",
];

export async function POST(request: Request) {
  try {
    const body = await request.json() as Partial<{ deviceId: string; action: DecisionAction; operator: string; note: string }>;
    if (!body.deviceId || !body.action || !ACTIONS.includes(body.action)) {
      return Response.json({ ok: false, error: "deviceId and a valid action are required." }, { status: 400 });
    }
    const state = getLiveTelemetryService().executeDecision(
      body.deviceId,
      body.action,
      body.operator ?? "operator",
      body.note ?? "",
    );
    return Response.json({ ok: true, state }, { headers: { "cache-control": "no-store" } });
  } catch (error) {
    return Response.json({ ok: false, error: error instanceof Error ? error.message : "Unable to execute decision." }, { status: 422 });
  }
}
