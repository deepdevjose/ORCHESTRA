import { randomUUID } from "node:crypto";
import mqtt, { MqttClient } from "mqtt";
import { createDemoTelemetry, DEMO_MACHINE_PROFILES } from "./demo";
import { scoreTelemetry } from "./model-client";
import {
  DashboardState,
  DecisionAction,
  FEATURE_DEFINITIONS,
  FleetMachine,
  TelemetryPayload,
  TelemetryRecord,
} from "./types";

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

function machineFromProfile(profile: (typeof DEMO_MACHINE_PROFILES)[number]): FleetMachine {
  return {
    deviceId: profile.deviceId,
    stationId: profile.stationId,
    name: profile.name,
    location: profile.location,
    line: profile.line,
    asset: profile.asset,
    operationalState: "production",
    source: "demo",
    scenario: "awaiting telemetry",
    lastSeen: "",
    current: null,
    urgency: 0,
    uncertainty: 0,
    label: "low",
    recommendation: "do_nothing",
    humanReview: false,
    trend: [],
  };
}

class LiveTelemetryService {
  private started = false;
  private startedAt = 0;
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
      asset: "Laser welding fleet",
    },
    model: { name: "initialising", version: "pending", source: "fallback" },
    current: null,
    history: [],
    fleet: DEMO_MACHINE_PROFILES.map(machineFromProfile),
    selectedDeviceId: DEMO_MACHINE_PROFILES[0].deviceId,
    decisions: [],
    modelTelemetry: {
      framesPerMinute: 0,
      averageUrgency: 0,
      averageUncertainty: 0,
      highRiskMachines: 0,
      reviewQueue: 0,
      modelEvents: [],
    },
    simulation: { enabled: true, machineCount: DEMO_MACHINE_PROFILES.length, label: "SYNTHETIC LAB SIMULATION" },
    alerts: [],
    totals: { messages: 0, reviews: 0, overrides: 0, mqttMessages: 0 },
    updatedAt: now(),
  };

  start() {
    if (this.started) return;
    this.started = true;
    this.startedAt = Date.now();
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

  executeDecision(deviceId: string, action: DecisionAction, operator: string, note: string) {
    this.start();
    const machine = this.state.fleet.find((item) => item.deviceId === deviceId);
    if (!machine) throw new Error("Unknown machine: " + deviceId);
    const nextState: FleetMachine["operationalState"] = action === "urgent_intervention"
      ? "stopped"
      : action === "hold_production" || action === "schedule_major_maintenance"
        ? "maintenance_hold"
        : action === "inspect"
          ? "inspection"
          : action === "schedule_minor_maintenance"
            ? "maintenance_planned"
            : action === "resume_production"
              ? "production"
              : machine.operationalState;
    const connected = Boolean(this.mqttClient?.connected);
    const decision = {
      id: randomUUID(),
      timestamp: now(),
      deviceId,
      machineName: machine.name,
      action,
      operator: operator.trim() || "operator",
      note: note.trim() || "No operator note supplied.",
      transport: connected ? "mqtt" as const : "simulated" as const,
      status: connected ? "published" as const : "accepted" as const,
    };
    if (connected) {
      this.mqttClient?.publish(this.commandTopicFor(deviceId), JSON.stringify({
        device_id: deviceId,
        action,
        operator: decision.operator,
        note: decision.note,
        timestamp: decision.timestamp,
        source: "orchestra-dashboard",
      }), { qos: 0 });
    }
    this.state = {
      ...this.state,
      selectedDeviceId: deviceId,
      fleet: this.state.fleet.map((item) => item.deviceId === deviceId ? { ...item, operationalState: nextState } : item),
      decisions: [decision, ...this.state.decisions].slice(0, 30),
      alerts: [{
        id: decision.id,
        timestamp: decision.timestamp,
        title: `Operator action · ${action.replaceAll("_", " ")}`,
        detail: `${machine.name} · ${decision.note}`,
        level: action === "urgent_intervention" ? "critical" as const : "warning" as const,
      }, ...this.state.alerts].slice(0, 12),
      updatedAt: now(),
    };
    this.emit();
    return this.state;
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
    void this.ingestDemoBatch();
    this.demoTimer = setInterval(() => {
      if (!this.mqttClient?.connected) void this.ingestDemoBatch();
    }, 2200);
  }

  private async ingestDemoBatch() {
    const sequence = this.demoSequence++;
    await Promise.all(DEMO_MACHINE_PROFILES.map((_, index) => this.ingest(createDemoTelemetry(sequence, index), "demo")));
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

  private commandTopicFor(deviceId: string) {
    const configured = process.env.MQTT_COMMAND_TOPIC;
    if (configured) return configured.replace("{device_id}", deviceId);
    return `orchestra/laser-welding/${deviceId}/command`;
  }

  private addAlert(title: string, detail: string, level: "info" | "warning" | "critical") {
    this.state = {
      ...this.state,
      alerts: [{ id: randomUUID(), timestamp: now(), title, detail, level }, ...this.state.alerts].slice(0, 12),
      updatedAt: now(),
    };
    this.emit();
  }

  private normalise(payload: TelemetryPayload): { features: Record<string, number>; stationId: string; deviceId: string; scenario: string; timestamp: string; machineName: string; location: string; line: string } {
    const nested = payload.features ?? {};
    const features = Object.fromEntries(FEATURE_DEFINITIONS.map(({ key }) => [key, Number(nested[key] ?? payload[key])]));
    const invalid = Object.entries(features).filter(([, value]) => !Number.isFinite(value));
    if (invalid.length) throw new Error("Missing or invalid sensor fields: " + invalid.map(([key]) => key).join(", "));
    const knownProfile = DEMO_MACHINE_PROFILES.find((profile) => profile.deviceId === payload.device_id || profile.stationId === payload.station_id);
    return {
      features,
      stationId: String(payload.station_id ?? knownProfile?.stationId ?? this.state.station.id),
      deviceId: String(payload.device_id ?? knownProfile?.deviceId ?? "esp32-unknown"),
      scenario: String(payload.scenario ?? "live"),
      timestamp: payload.timestamp ?? now(),
      machineName: String(payload.machine_name ?? knownProfile?.name ?? payload.device_id ?? "Unregistered cell"),
      location: String(payload.location ?? knownProfile?.location ?? "Unknown location"),
      line: String(payload.line ?? knownProfile?.line ?? "Unassigned line"),
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
      const previous = this.state.fleet.find((item) => item.deviceId === record.deviceId);
      const machine: FleetMachine = {
        deviceId: record.deviceId,
        stationId: record.stationId,
        name: normalised.machineName,
        location: normalised.location,
        line: normalised.line,
        asset: previous?.asset ?? "SIASUN SR12A",
        operationalState: previous?.operationalState ?? "production",
        source,
        scenario: record.scenario,
        lastSeen: record.receivedAt,
        current: record,
        urgency: inference.adjustedUrgency,
        uncertainty: inference.uncertainty,
        label: inference.label,
        recommendation: inference.recommendation,
        humanReview: inference.humanReview,
        trend: [...(previous?.trend ?? []), inference.adjustedUrgency].slice(-16),
      };
      const fleet = previous
        ? this.state.fleet.map((item) => item.deviceId === record.deviceId ? machine : item)
        : [...this.state.fleet, machine];
      const currentFleet = fleet.filter((item) => item.current);
      const averageUrgency = currentFleet.length ? currentFleet.reduce((sum, item) => sum + item.urgency, 0) / currentFleet.length : 0;
      const averageUncertainty = currentFleet.length ? currentFleet.reduce((sum, item) => sum + item.uncertainty, 0) / currentFleet.length : 0;
      const modelEvent = inference.humanReview ? {
        id: record.id,
        timestamp: record.timestamp,
        deviceId: record.deviceId,
        event: "Human review gate opened",
        detail: inference.qualityFlags.length ? inference.qualityFlags.join(" · ") : "Model uncertainty or urgency crossed the review threshold.",
        level: inference.adjustedUrgency >= 82 ? "critical" as const : "warning" as const,
      } : null;
      const alertLevel = levelFor(record);
      const newAlert = alertLevel === "info" ? [] : [{
        id: record.id,
        timestamp: record.timestamp,
        title: inference.humanReview ? "Human review requested" : "Maintenance risk elevated",
        detail: `${machine.name} · ${inference.qualityFlags.length ? inference.qualityFlags.join(" · ") : "Review the AI recommendation before scheduling."}`,
        level: alertLevel,
      }];
      const selected = fleet.find((item) => item.deviceId === this.state.selectedDeviceId);
      const elapsedMinutes = Math.max((Date.now() - this.startedAt) / 60000, 1 / 60);
      this.state = {
        ...this.state,
        connection: source === "mqtt" ? "mqtt" : this.state.connection === "mqtt" ? "mqtt" : this.state.connection,
        model: {
          name: inference.modelName,
          version: inference.modelVersion,
          source: inference.modelName === "fallback_rule" ? "fallback" : "python",
        },
        current: selected?.current ?? record,
        history: [...this.state.history, record].slice(-80),
        fleet,
        alerts: [...newAlert, ...this.state.alerts].slice(0, 12),
        modelTelemetry: {
          framesPerMinute: Math.round((this.state.totals.messages + 1) / elapsedMinutes),
          averageUrgency,
          averageUncertainty,
          highRiskMachines: currentFleet.filter((item) => item.urgency >= 70).length,
          reviewQueue: currentFleet.filter((item) => item.humanReview && item.operationalState === "production").length,
          modelEvents: modelEvent ? [modelEvent, ...this.state.modelTelemetry.modelEvents].slice(0, 20) : this.state.modelTelemetry.modelEvents,
        },
        simulation: { ...this.state.simulation, enabled: source === "demo" ? true : this.state.simulation.enabled, machineCount: fleet.length },
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
