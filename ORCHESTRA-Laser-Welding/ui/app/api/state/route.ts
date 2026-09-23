import { getLiveTelemetryService } from "../../../lib/live-service";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(getLiveTelemetryService().getState(), {
    headers: { "cache-control": "no-store" },
  });
}
