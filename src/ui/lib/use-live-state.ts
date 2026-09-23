"use client";

import { useEffect, useState } from "react";
import { DashboardState } from "./types";

export function useLiveState() {
  const [state, setState] = useState<DashboardState | null>(null);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "live" | "reconnecting">("connecting");

  useEffect(() => {
    let active = true;
    const eventSource = new EventSource("/api/stream");
    eventSource.onopen = () => {
      if (active) setStreamStatus("live");
    };
    eventSource.onmessage = (event) => {
      if (!active) return;
      try {
        setState(JSON.parse(event.data) as DashboardState);
      } catch {
        setStreamStatus("reconnecting");
      }
    };
    eventSource.onerror = () => {
      if (active) setStreamStatus("reconnecting");
    };
    return () => {
      active = false;
      eventSource.close();
    };
  }, []);

  return { state, setState, streamStatus };
}
