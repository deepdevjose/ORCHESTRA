import { getLiveTelemetryService } from "../../../lib/live-service";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const state = getLiveTelemetryService().getState();
  return Response.json({
    ok: true,
    connection: state.connection,
    model: state.model,
    messages: state.totals.messages,
    updatedAt: state.updatedAt,
  });
}
