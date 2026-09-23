import { getLiveTelemetryService } from "../../../lib/live-service";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const encoder = new TextEncoder();
  const service = getLiveTelemetryService();
  let unsubscribe = () => {};
  const stream = new ReadableStream({
    start(controller) {
      let closed = false;
      const send = (state: unknown) => {
        if (closed) return;
        controller.enqueue(encoder.encode("data: " + JSON.stringify(state) + "\n\n"));
      };
      unsubscribe = service.subscribe(send);
      request.signal.addEventListener("abort", () => {
        closed = true;
        unsubscribe();
        try {
          controller.close();
        } catch {
          // The browser may close the stream before the server observes it.
        }
      });
    },
    cancel() {
      unsubscribe();
    },
  });
  return new Response(stream, {
    headers: {
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "content-type": "text/event-stream",
    },
  });
}
