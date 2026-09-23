import { randomUUID } from "node:crypto";
import mqtt, { MqttClient } from "mqtt";
import { createDemoTelemetry } from "./demo";
import { scoreTelemetry } from "./model-client";
import { DashboardState, FEATURE_DEFINITIONS, TelemetryPayload, TelemetryRecord } from "./types";

type StateListener = (state: DashboardState) => void;
const GLOBAL_KEY = "__orchestra_live_service__";

function now() {
  return new Date().toISOString();
}

function levelFor(record: TelemetryRecord): "info" | "warning" | "critical" {
  if (record.inference.adjustedUrgency >= 82) return "critical";
  if (record.inference.humanReview || record.inference.adjustedUrgency >= 40) return "warning";
  return "info";
}

class LiveTelemetryService {
  private started = false;
  private demoTimer: NodeJS.Timeout | undefined;
  private demoSequence = 1;
  private mqttClient: MqttClient | undefined;
  private listeners = new Set<StateListener>();
  private state: DashboardState = {
    connection: "demo",
    brokerUrl: process.env.MQTT_BROKER_URL ?? "not configured",
    mqttTopic: process.env.MQTT_TOPIC ?? "orchestra/laser-welding/+/telemetry",
    station: {
      id: process.env.ORCHESTRA_STATION_ID ?? "CN-SUZHOU-LW-01",
      location: "Suzhou · Jiangsu",
      line: "Automotive battery enclosure",
      asset: "Laser welding cell 01",
    },
    model: { name: "initialising", version: "pending", source: "fallback" },
    current: null,
    history: [],
    alerts: [],
    totals: { messages: 0, reviews: 0, overrides: 0, mqttMessages: 0 },
    updatedAt: now(),
  };

  start() {
    if (this.started) return;
    this.started = true;
    this.beginDemo();
    if (process.env.MQTT_BROKER_URL) this.connectMqtt();
  }

  getState() {
    this.start();
    return this.state;
  }

  subscribe(listener: StateListener) {
    this.start();
    this.listeners.add(listener);
    listener(this.state);
    return () => this.listeners.delete(listener);
  }

  private emit() {
    for (const listener of this.listeners) listener(this.state);
  }

  private setConnection(connection: DashboardState["connection"]) {
    this.state = { ...this.state, connection, updatedAt: now() };
    this.emit();
  }

  private beginDemo() {
    if (this.demoTimer) return;
    this.setConnection(process.env.MQTT_BROKER_URL ? "connecting" : "demo");
    void this.ingest(createDemoTelemetry(this.demoSequence++), "demo");
    this.demoTimer = setInterval(() => {
      if (!this.mqttClient?.connected) void this.ingest(createDemoTelemetry(this.demoSequence++), "demo");
    }, 2200);
  }

  private stopDemo() {
    if (!this.demoTimer) return;
    clearInterval(this.demoTimer);
    this.demoTimer = undefined;
  }

  private connectMqtt() {
    const broker = process.env.MQTT_BROKER_URL as string;
    this.mqttClient = mqtt.connect(broker, {
      clientId: "orchestra-dashboard-" + Math.random().toString(16).slice(2),
      username: process.env.MQTT_USERNAME,
      password: process.env.MQTT_PASSWORD,
      reconnectPeriod: 5000,
      connectTimeout: 5000,
    });
    this.mqttClient.on("connect", () => {
      this.stopDemo();
      this.setConnection("mqtt");
      this.mqttClient?.subscribe(this.state.mqttTopic, { qos: 0 });
    });
    this.mqttClient.on("message", (topic, message) => {
      try {
        const parsed = JSON.parse(message.toString()) as TelemetryPayload;
        void this.ingest({ ...parsed, station_id: parsed.station_id ?? topic.split("/").at(-2) }, "mqtt");
      } catch {
        this.addAlert("Invalid MQTT payload", "The incoming frame could not be parsed as JSON.", "warning");
      }
    });
    this.mqttClient.on("reconnect", () => this.setConnection("connecting"));
    this.mqttClient.on("close", () => {
      if (!this.mqttClient?.connected) {
        this.setConnection("degraded");
        this.beginDemo();
      }
    });
    this.mqttClient.on("error", () => this.setConnection("degraded"));
  }

  private addAlert(title: string, detail: string, level: "info" | "warning" | "critical") {
    this.state = {
      ...this.state,
      alerts: [{ id: randomUUID(), timestamp: now(), title, detail, level }, ...this.state.alerts].slice(0, 8),
      updatedAt: now(),
    };
    this.emit();
  }

  private normalise(payload: TelemetryPayload): { features: Record<string, number>; stationId: string; deviceId: string; scenario: string; timestamp: string } {
    const nested = payload.features ?? {};
    const features = Object.fromEntries(FEATURE_DEFINITIONS.map(({ key }) => [key, Number(nested[key] ?? payload[key])]));
    const invalid = Object.entries(features).filter(([, value]) => !Number.isFinite(value));
    if (invalid.length) throw new Error("Missing or invalid sensor fields: " + invalid.map(([key]) => key).join(", "));
    return {
      features,
      stationId: String(payload.station_id ?? this.state.station.id),
      deviceId: String(payload.device_id ?? "esp32-unknown"),
      scenario: String(payload.scenario ?? "live"),
      timestamp: payload.timestamp ?? now(),
    };
  }

  private async ingest(payload: TelemetryPayload, source: "mqtt" | "demo") {
    try {
      const normalised = this.normalise(payload);
      const inference = await scoreTelemetry({ ...payload, features: normalised.features });
      const record: TelemetryRecord = {
        id: randomUUID(),
        timestamp: normalised.timestamp,
        receivedAt: now(),
        stationId: normalised.stationId,
        deviceId: normalised.deviceId,
        scenario: normalised.scenario,
        source,
        features: normalised.features as TelemetryRecord["features"],
        inference,
      };
      const alertLevel = levelFor(record);
      const newAlert = alertLevel === "info" ? [] : [{
        id: record.id,
        timestamp: record.timestamp,
        title: inference.humanReview ? "Human review requested" : "Maintenance risk elevated",
        detail: inference.qualityFlags.length ? inference.qualityFlags.join(" · ") : "Review the AI recommendation before scheduling.",
        level: alertLevel,
      }];
      this.state = {
        ...this.state,
        connection: source === "mqtt" ? "mqtt" : this.state.connection === "mqtt" ? "mqtt" : this.state.connection,
        model: {
          name: inference.modelName,
          version: inference.modelVersion,
          source: inference.modelName === "fallback_rule" ? "fallback" : "python",
        },
        current: record,
        history: [...this.state.history, record].slice(-36),
        alerts: [...newAlert, ...this.state.alerts].slice(0, 8),
        totals: {
          messages: this.state.totals.messages + 1,
          reviews: this.state.totals.reviews + (inference.humanReview ? 1 : 0),
          overrides: this.state.totals.overrides + (inference.humanOverride ? 1 : 0),
          mqttMessages: this.state.totals.mqttMessages + (source === "mqtt" ? 1 : 0),
        },
        updatedAt: now(),
      };
      this.emit();
    } catch (error) {
      this.addAlert("Telemetry validation failed", error instanceof Error ? error.message : "Unknown payload error.", "critical");
    }
  }
}

export function getLiveTelemetryService() {
  const globalScope = globalThis as typeof globalThis & { [GLOBAL_KEY]?: LiveTelemetryService };
  if (!globalScope[GLOBAL_KEY]) globalScope[GLOBAL_KEY] = new LiveTelemetryService();
  return globalScope[GLOBAL_KEY];
}
