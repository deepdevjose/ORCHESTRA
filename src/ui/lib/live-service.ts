import { randomUUID } from "node:crypto";
import mqtt, { MqttClient } from "mqtt";
import { createDemoTelemetry, DEMO_MACHINE_PROFILES } from "./demo";
import { scoreTelemetry } from "./model-client";
import {
  AgentDecisionTrace,
  DashboardState,
  DecisionAction,
  FEATURE_DEFINITIONS,
  FleetMachine,
  ProductionOrder,
  TelemetryPayload,
  TelemetryRecord,
} from "./types";

type StateListener = (state: DashboardState) => void;
type SyntheticRuntime = {
  health: number;
  serviceWear: number;
  maintenanceCount: number;
  shiftId: string;
  shiftLoadPieces: number;
  piecesProduced: number;
  piecesRemaining: number;
  cooldownTicks: number;
  pieceAccumulator: number;
};
const GLOBAL_KEY = "__orchestra_live_service__";
const DEMO_TICK_MS = 2200;
const SIMULATION_SECONDS_PER_TICK = 10;
const CYCLE_TIME_SECONDS_PER_CELL = 60;
const FLEET_PIECES_PER_SECOND = DEMO_MACHINE_PROFILES.length / CYCLE_TIME_SECONDS_PER_CELL;

function now() {
  return new Date().toISOString();
}

function levelFor(record: TelemetryRecord): "info" | "warning" | "critical" {
  if (record.inference.adjustedUrgency >= 82) return "critical";
  if (record.inference.humanReview || record.inference.adjustedUrgency >= 40) return "warning";
  return "info";
}

function smoothValue(previous: number | undefined, next: number, alpha: number, maxStep: number) {
  if (previous === undefined || !Number.isFinite(previous) || !Number.isFinite(next)) return next;
  const delta = (next - previous) * alpha;
  return previous + Math.sign(delta) * Math.min(Math.abs(delta), maxStep);
}

function smoothFeatures(previous: TelemetryRecord["features"] | undefined, next: Record<string, number>) {
  if (!previous) return next;
  return Object.fromEntries(Object.entries(next).map(([key, value]) => [
    key,
    smoothValue(previous[key as keyof typeof previous], value, 0.24, Math.max(Math.abs(value) * 0.08, 0.02)),
  ]));
}

function freshAgentTrace(): AgentDecisionTrace[] {
  return [
    { agent: "telemetry_quality", label: "Agent 1 · Telemetry quality", status: "pass", decision: "Awaiting frame", detail: "Validates the 17-feature contract, source and quality flags.", timestamp: now() },
    { agent: "predictive_inference", label: "Agent 2 · Predictive risk", status: "pass", decision: "Awaiting frame", detail: "Scores urgency, process instability and uncertainty.", timestamp: now() },
    { agent: "shift_scheduler", label: "Agent 3 · Shift scheduler", status: "pass", decision: "Awaiting order", detail: "Bounds production, checkpoints and maintenance actions.", timestamp: now() },
  ];
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
    shiftId: "awaiting shift",
    shiftLoadPieces: 0,
    piecesProduced: 0,
    piecesRemaining: 0,
    health: 0,
    lifetimePercent: 100,
    maintenanceCount: 0,
    serviceWear: 0,
    dataQuality: "valid",
    agentTrace: freshAgentTrace(),
    productionPlan: { maxAdditionalPieces: 0, reevaluateEveryPieces: 0, action: "stop_and_review" },
  };
}

function shiftLoadFor() { return 1000; }

class LiveTelemetryService {
  private started = false;
  private startedAt = 0;
  private demoTimer: NodeJS.Timeout | undefined;
  private demoSequence = 1;
  private mqttClient: MqttClient | undefined;
  private syntheticRuntime = new Map<string, SyntheticRuntime>();
  private listeners = new Set<StateListener>();
  private orderPieceAccumulator = 0;
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
    simulation: {
      enabled: true,
      machineCount: DEMO_MACHINE_PROFILES.length - 1,
      label: "1 EDGE + 9 SYNTHETIC",
      failureHorizonMinutes: 60,
      productionOrder: null,
      checkpointCount: 0,
      lastCheckpointAt: null,
      cycleTimeSecondsPerCell: CYCLE_TIME_SECONDS_PER_CELL,
      fleetPiecesPerSecond: FLEET_PIECES_PER_SECOND,
      simulationSecondsPerTick: SIMULATION_SECONDS_PER_TICK,
    },
    alerts: [],
    totals: { messages: 0, reviews: 0, overrides: 0, mqttMessages: 0 },
    updatedAt: now(),
  };

  /** Start synthetic telemetry and optionally connect to the configured MQTT broker. */
  start() {
    if (this.started) return;
    this.started = true;
    this.startedAt = Date.now();
    this.beginDemo();
    if (process.env.MQTT_BROKER_URL) this.connectMqtt();
  }

  /** Return the current dashboard snapshot, starting the service on first access. */
  getState() {
    this.start();
    return this.state;
  }

  /** Register a state listener and immediately deliver the current snapshot. */
  subscribe(listener: StateListener) {
    this.start();
    this.listeners.add(listener);
    listener(this.state);
    return () => this.listeners.delete(listener);
  }

  /** Start a production order and reset fleet progress to the new shift baseline. */
  configureOrder(targetPieces: number, productType = "Large automotive chassis", shiftLengthMinutes = 480) {
    this.start();
    const target = Math.min(1_000_000, Math.max(1, Math.round(targetPieces)));
    const checkpointEveryPieces = Math.max(1, Math.ceil(target / 10));
    const order: ProductionOrder = {
      id: `ORD-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`,
      productType: productType.trim() || "Large automotive chassis",
      targetPieces: target,
      completedPieces: 0,
      remainingPieces: target,
      shiftId: "SHIFT-01",
      shiftLengthMinutes: Math.max(1, Math.round(shiftLengthMinutes)),
      checkpointEveryPieces,
      lastCheckpointPieces: 0,
      nextCheckpointPieces: checkpointEveryPieces,
      fleetPiecesPerSecond: FLEET_PIECES_PER_SECOND,
      cycleTimeSecondsPerCell: CYCLE_TIME_SECONDS_PER_CELL,
      simulationSecondsPerTick: SIMULATION_SECONDS_PER_TICK,
      status: "running",
      assumption: "10 independent cells × 1 chassis / 60 s; accelerated clock: 10 simulated seconds per dashboard tick.",
    };
    this.orderPieceAccumulator = 0;
    this.syntheticRuntime.clear();
    this.state = {
      ...this.state,
      current: null,
      history: [],
      decisions: [],
      alerts: [{ id: randomUUID(), timestamp: now(), title: "Production order started", detail: `${order.id} · ${order.targetPieces.toLocaleString()} pieces · ${order.shiftId}`, level: "info" as const }, ...this.state.alerts].slice(0, 12),
      fleet: this.state.fleet.map((machine) => ({
        ...machine,
        operationalState: "production",
        current: null,
        urgency: 0,
        uncertainty: 0,
        trend: [],
        shiftId: order.shiftId,
        shiftLoadPieces: order.targetPieces,
        piecesProduced: 0,
        piecesRemaining: order.targetPieces,
        health: 0,
        lifetimePercent: 100,
        maintenanceCount: 0,
        serviceWear: 0,
        agentTrace: freshAgentTrace(),
      })),
      simulation: { ...this.state.simulation, productionOrder: order, checkpointCount: 0, lastCheckpointAt: null },
      updatedAt: now(),
    };
    this.emit();
    return this.state;
  }

  /** Clear order progress, checkpoints, traces, and synthetic machine wear. */
  resetSimulation() {
    this.start();
    const timestamp = now();
    for (const machine of this.state.fleet) {
      if (this.mqttClient?.connected) this.publishResetLifetime(machine.deviceId, timestamp);
    }
    this.syntheticRuntime.clear();
    this.orderPieceAccumulator = 0;
    this.demoSequence = 1;
    this.state = {
      ...this.state,
      current: null,
      history: [],
      decisions: [],
      alerts: [{ id: randomUUID(), timestamp, title: "Simulation reset", detail: "Order, checkpoints, maintenance wear and robot lifetime restored to setup state.", level: "info" as const }, ...this.state.alerts].slice(0, 12),
      fleet: this.state.fleet.map((machine) => ({
        ...machine,
        operationalState: "production",
        current: null,
        urgency: 0,
        uncertainty: 0,
        trend: [],
        shiftId: "awaiting shift",
        shiftLoadPieces: 0,
        piecesProduced: 0,
        piecesRemaining: 0,
        health: 0,
        lifetimePercent: 100,
        maintenanceCount: 0,
        serviceWear: 0,
        agentTrace: freshAgentTrace(),
      })),
      simulation: { ...this.state.simulation, productionOrder: null, checkpointCount: 0, lastCheckpointAt: null },
      totals: { messages: 0, reviews: 0, overrides: 0, mqttMessages: 0 },
      updatedAt: timestamp,
    };
    this.emit();
    return this.state;
  }

  /** Apply an operator decision locally and publish it over MQTT when connected. */
  executeDecision(deviceId: string, action: DecisionAction, operator: string, note: string) {
    this.start();
    const machine = this.state.fleet.find((item) => item.deviceId === deviceId);
    if (!machine) throw new Error("Unknown machine: " + deviceId);
    const nextState: FleetMachine["operationalState"] = action === "reset_lifetime"
      ? "production"
      : action === "urgent_intervention"
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
    const runtime = this.syntheticRuntime.get(deviceId);
    if (runtime && action === "reset_lifetime") {
      runtime.health = 0;
      runtime.serviceWear = 0;
      runtime.maintenanceCount = 0;
      runtime.cooldownTicks = 0;
    }
    if (runtime && (action === "schedule_minor_maintenance" || action === "schedule_major_maintenance")) {
      runtime.maintenanceCount += 1;
      runtime.serviceWear = Math.min(0.45, runtime.serviceWear + 0.04);
      runtime.health = Math.max(0.02, runtime.serviceWear);
      runtime.cooldownTicks = action === "schedule_minor_maintenance" ? 8 : 14;
    } else if (runtime && action === "urgent_intervention") {
      runtime.health = Math.max(runtime.health, 0.06);
      runtime.cooldownTicks = 14;
    }
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
    const maintenanceCommand = action === "schedule_minor_maintenance" || action === "schedule_major_maintenance";
    const immediateWear = runtime?.serviceWear ?? (maintenanceCommand ? Math.min(0.45, machine.serviceWear + 0.04) : machine.serviceWear);
    const immediateMaintenanceCount = runtime?.maintenanceCount ?? (maintenanceCommand ? machine.maintenanceCount + 1 : machine.maintenanceCount);
    const runtimeState = action === "reset_lifetime"
      ? { health: 0, lifetimePercent: 100, maintenanceCount: 0, serviceWear: 0 }
      : (runtime || maintenanceCommand) ? {
        health: runtime?.health ?? Math.max(0.02, immediateWear),
        lifetimePercent: Math.max(0, 100 - immediateWear * 100),
        maintenanceCount: immediateMaintenanceCount,
        serviceWear: immediateWear,
      } : {};
    this.state = {
      ...this.state,
      selectedDeviceId: deviceId,
      fleet: this.state.fleet.map((item) => item.deviceId === deviceId ? { ...item, operationalState: nextState, ...runtimeState } : item),
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

  private publishResetLifetime(deviceId: string, timestamp = now()) {
    this.mqttClient?.publish(this.commandTopicFor(deviceId), JSON.stringify({
      device_id: deviceId,
      action: "reset_lifetime",
      operator: "simulation-reset",
      note: "Restore simulated robot and ESP32 firmware lifetime to 100%.",
      timestamp,
      source: "orchestra-dashboard",
    }), { qos: 1 });
  }

  /** Publish a scenario command for an MQTT-connected edge device. */
  publishScenario(deviceId: string, scenario: string) {
    this.start();
    const machine = this.state.fleet.find((item) => item.deviceId === deviceId);
    if (!machine) throw new Error("Unknown machine: " + deviceId);
    const connected = Boolean(this.mqttClient?.connected);
    if (!connected) throw new Error("MQTT is not connected; scenario commands require the ESP32 broker path.");
    this.mqttClient?.publish(this.commandTopicFor(deviceId), JSON.stringify({
      device_id: deviceId,
      command: "set_scenario",
      scenario,
      timestamp: now(),
      source: "orchestra-dashboard",
    }), { qos: 1 });
    this.addAlert("Scenario command published", `${machine.name} · ${scenario}`, "info");
    return this.state;
  }

  /** Update the displayed simulation horizon without changing the research model. */
  setFailureHorizon(minutes: number) {
    this.start();
    const failureHorizonMinutes = Math.min(60, Math.max(5, Math.round(minutes)));
    this.state = {
      ...this.state,
      simulation: { ...this.state.simulation, failureHorizonMinutes },
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
      // Keep the nine synthetic cells running even when the first ESP32 cell is
      // connected. The dashboard is intentionally a mixed edge + lab fleet.
      void this.ingestDemoBatch();
    }, DEMO_TICK_MS);
  }

  private async ingestDemoBatch() {
    const sequence = this.demoSequence++;
    this.advanceProductionOrder();
    const liveDeviceId = process.env.ORCHESTRA_LIVE_DEVICE_ID ?? DEMO_MACHINE_PROFILES[0].deviceId;
    const profiles = process.env.MQTT_BROKER_URL
      ? DEMO_MACHINE_PROFILES.filter((profile) => profile.deviceId !== liveDeviceId)
      : DEMO_MACHINE_PROFILES;
    await Promise.all(profiles.map((profile) => {
      const index = DEMO_MACHINE_PROFILES.indexOf(profile);
      let runtime = this.syntheticRuntime.get(profile.deviceId);
      if (!runtime) {
        const shiftLoadPieces = this.state.simulation.productionOrder?.targetPieces ?? shiftLoadFor();
        runtime = {
          health: profile.riskBias * 0.18,
          serviceWear: 0,
          maintenanceCount: 0,
          shiftId: `shift-${Math.floor(sequence / 40) + 1}`,
          shiftLoadPieces,
          piecesProduced: 0,
          piecesRemaining: shiftLoadPieces,
          cooldownTicks: 0,
          pieceAccumulator: 0,
        };
        this.syntheticRuntime.set(profile.deviceId, runtime);
      }
      const order = this.state.simulation.productionOrder;
      const shiftLoadPieces = order?.targetPieces ?? shiftLoadFor();
      if (runtime.shiftLoadPieces !== shiftLoadPieces || (order && runtime.shiftId !== order.shiftId)) {
        runtime.shiftLoadPieces = shiftLoadPieces;
        runtime.shiftId = order?.shiftId ?? `shift-${Math.floor(sequence / 40) + 1}`;
      }
      if (order) {
        runtime.piecesProduced = order.completedPieces;
        runtime.piecesRemaining = order.remainingPieces;
      }
      if (runtime.cooldownTicks > 0) runtime.cooldownTicks -= 1;
      const loadFactor = order ? 0.6 : 0.25;
      const horizonTicks = this.state.simulation.failureHorizonMinutes * 60_000 / DEMO_TICK_MS;
      const degradationRate = (1 / horizonTicks) * (0.55 + loadFactor * 1.2) * (1 + runtime.health * 2.2);
      if (runtime.cooldownTicks > 0) {
        runtime.health = Math.max(runtime.serviceWear, runtime.health - 0.02);
      } else {
        runtime.health = Math.min(1, Math.max(runtime.serviceWear, runtime.health + degradationRate));
      }
      return this.ingest(createDemoTelemetry(sequence, index, runtime), "demo");
    }));
  }

  private advanceProductionOrder() {
    const order = this.state.simulation.productionOrder;
    if (!order || order.status !== "running") return;
    this.orderPieceAccumulator += order.fleetPiecesPerSecond * order.simulationSecondsPerTick;
    const produced = Math.min(order.remainingPieces, Math.floor(this.orderPieceAccumulator));
    if (produced <= 0) return;
    this.orderPieceAccumulator -= produced;
    const completedPieces = order.completedPieces + produced;
    const remainingPieces = order.targetPieces - completedPieces;
    let checkpointCount = this.state.simulation.checkpointCount;
    let lastCheckpointPieces = order.lastCheckpointPieces;
    let nextCheckpointPieces = order.nextCheckpointPieces;
    let lastCheckpointAt = this.state.simulation.lastCheckpointAt;
    while (completedPieces >= nextCheckpointPieces && nextCheckpointPieces <= order.targetPieces) {
      checkpointCount += 1;
      lastCheckpointPieces = nextCheckpointPieces;
      nextCheckpointPieces = Math.min(order.targetPieces + 1, nextCheckpointPieces + order.checkpointEveryPieces);
      lastCheckpointAt = now();
    }
    const shiftCapacity = Math.max(1, Math.floor(order.fleetPiecesPerSecond * order.shiftLengthMinutes * 60));
    const shiftNumber = Math.floor(completedPieces / shiftCapacity) + 1;
    const nextOrder: ProductionOrder = {
      ...order,
      completedPieces,
      remainingPieces,
      shiftId: `SHIFT-${String(shiftNumber).padStart(2, "0")}`,
      lastCheckpointPieces,
      nextCheckpointPieces,
      status: remainingPieces <= 0 ? "completed" : "running",
    };
    this.state = {
      ...this.state,
      simulation: { ...this.state.simulation, productionOrder: nextOrder, checkpointCount, lastCheckpointAt },
      updatedAt: now(),
    };
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
      const previous = this.state.fleet.find((item) => item.deviceId === normalised.deviceId);
      const modelInference = await scoreTelemetry({ ...payload, features: normalised.features });
      const qualityFlags = [...modelInference.qualityFlags];
      const atypical = payload.data_quality === "atypical" || normalised.features.cooling_system_alarm > 0.5 || normalised.features.shielding_gas_flow_l_min < 10 || normalised.features.vibration_rms > 0.3;
      if (atypical && !qualityFlags.includes("Atypical telemetry · Agent 1 review")) qualityFlags.push("Atypical telemetry · Agent 1 review");
      const syntheticRuntime = source === "demo" ? this.syntheticRuntime.get(normalised.deviceId) : undefined;
      const rawAdjustedUrgency = Math.max(modelInference.adjustedUrgency, source === "demo" ? Number(payload.simulated_risk ?? 0) * 100 : 0, atypical ? 72 : 0);
      const adjustedUrgency = smoothValue(previous?.urgency, rawAdjustedUrgency, 0.22, 4.2);
      const predictedUrgency = smoothValue(previous?.current?.inference.predictedUrgency, modelInference.predictedUrgency, 0.22, 4.2);
      const uncertainty = smoothValue(previous?.uncertainty, modelInference.uncertainty, 0.2, 0.035);
      const processInstability = smoothValue(previous?.current?.inference.processInstability, modelInference.processInstability, 0.22, 0.04);
      const humanReview = previous?.humanReview
        ? adjustedUrgency >= 55 || uncertainty >= 0.30
        : modelInference.humanReview || atypical || adjustedUrgency >= 70 || uncertainty >= 0.45;
      const operationalState = syntheticRuntime && syntheticRuntime.cooldownTicks === 0 && previous && ["maintenance_planned", "maintenance_hold", "stopped"].includes(previous.operationalState)
        ? "production"
        : undefined;
      const inference = {
        ...modelInference,
        predictedUrgency,
        adjustedUrgency,
        uncertainty,
        processInstability,
        humanReview,
        label: adjustedUrgency > 70 ? "high" as const : adjustedUrgency > 40 ? "medium" as const : "low" as const,
        recommendation: adjustedUrgency >= 82 ? "urgent_intervention" as const : adjustedUrgency >= 65 || humanReview ? "inspect" as const : "do_nothing" as const,
        qualityFlags,
      };
      const displayedFeatures = smoothFeatures(previous?.current?.features, normalised.features) as TelemetryRecord["features"];
      const record: TelemetryRecord = {
        id: randomUUID(),
        timestamp: normalised.timestamp,
        receivedAt: now(),
        stationId: normalised.stationId,
        deviceId: normalised.deviceId,
        scenario: normalised.scenario,
        source,
        features: displayedFeatures,
        inference,
      };
      const activeOrder = this.state.simulation.productionOrder;
      const shiftId = String(activeOrder?.shiftId ?? payload.shift_id ?? previous?.shiftId ?? "live shift");
      const shiftLoadPieces = Number(activeOrder?.targetPieces ?? payload.shift_load_pieces ?? previous?.shiftLoadPieces ?? 0);
      const piecesProduced = Number(activeOrder?.completedPieces ?? payload.pieces_produced ?? previous?.piecesProduced ?? 0);
      const piecesRemaining = Number(activeOrder?.remainingPieces ?? payload.pieces_remaining ?? previous?.piecesRemaining ?? 0);
      const serviceWear = Math.min(1, Math.max(0, Number(payload.service_wear ?? syntheticRuntime?.serviceWear ?? previous?.serviceWear ?? 0)));
      const maintenanceCount = Math.max(0, Math.round(Number(payload.maintenance_count ?? syntheticRuntime?.maintenanceCount ?? previous?.maintenanceCount ?? 0)));
      const lifetimePercent = Math.max(0, Math.min(100, Number(payload.lifetime_percent ?? (100 - serviceWear * 100))));
      const productionPlan = adjustedUrgency >= 82 || atypical
        ? { maxAdditionalPieces: 0, reevaluateEveryPieces: 1, action: "stop_and_review" as const }
        : adjustedUrgency >= 40
          ? { maxAdditionalPieces: Math.min(piecesRemaining, this.state.simulation.productionOrder?.checkpointEveryPieces ?? 200), reevaluateEveryPieces: this.state.simulation.productionOrder?.checkpointEveryPieces ?? 200, action: "reduce_load" as const }
          : { maxAdditionalPieces: Math.min(piecesRemaining, this.state.simulation.productionOrder?.checkpointEveryPieces ?? 1000), reevaluateEveryPieces: this.state.simulation.productionOrder?.checkpointEveryPieces ?? 1000, action: "continue" as const };
      const traceTimestamp = record.receivedAt;
      const agentTrace: AgentDecisionTrace[] = [
        {
          agent: "telemetry_quality",
          label: "Agent 1 · Telemetry quality",
          status: atypical ? "review" : "pass",
          decision: atypical ? "Escalate frame" : "Accept frame",
          detail: `${FEATURE_DEFINITIONS.length}/${FEATURE_DEFINITIONS.length} fields · ${source.toUpperCase()} · ${qualityFlags.length ? qualityFlags.join(" · ") : "no quality flags"}`,
          timestamp: traceTimestamp,
        },
        {
          agent: "predictive_inference",
          label: "Agent 2 · Predictive risk",
          status: humanReview ? "review" : "pass",
          decision: `${inference.label.toUpperCase()} · ${inference.recommendation.replaceAll("_", " ")}`,
          detail: `Adjusted urgency ${adjustedUrgency.toFixed(1)} · uncertainty ${(uncertainty * 100).toFixed(0)}% · ${inference.modelName}`,
          timestamp: traceTimestamp,
        },
        {
          agent: "shift_scheduler",
          label: "Agent 3 · Shift scheduler",
          status: productionPlan.action === "stop_and_review" ? "hold" : productionPlan.action === "reduce_load" ? "review" : "pass",
          decision: productionPlan.action === "stop_and_review" ? "Stop at checkpoint" : productionPlan.action === "reduce_load" ? "Reduce load" : "Continue bounded order",
          detail: `${shiftId} · ${piecesRemaining.toLocaleString()} remaining · checkpoint every ${productionPlan.reevaluateEveryPieces.toLocaleString()}`,
          timestamp: traceTimestamp,
        },
      ];
      const machine: FleetMachine = {
        deviceId: record.deviceId,
        stationId: record.stationId,
        name: normalised.machineName,
        location: normalised.location,
        line: normalised.line,
        asset: previous?.asset ?? "SIASUN SR12A",
        operationalState: source === "mqtt" && payload.operational_state
          ? payload.operational_state
          : operationalState ?? previous?.operationalState ?? "production",
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
        shiftId,
        shiftLoadPieces,
        piecesProduced,
        piecesRemaining,
        health: Number(payload.simulated_health ?? previous?.health ?? 0),
        lifetimePercent,
        maintenanceCount,
        serviceWear,
        dataQuality: payload.data_quality === "atypical" || atypical ? "atypical" : "valid",
        agentTrace,
        productionPlan,
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
        level: atypical || inference.adjustedUrgency >= 82 ? "critical" as const : "warning" as const,
      } : null;
      const alertLevel = levelFor(record);
      const newAlert = alertLevel === "info" ? [] : [{
        id: record.id,
        timestamp: record.timestamp,
        title: inference.humanReview ? "Human review requested" : "Maintenance risk elevated",
        detail: `${machine.name} · ${inference.qualityFlags.length ? inference.qualityFlags.join(" · ") : "Review the AI recommendation before scheduling."}`,
        level: atypical ? "critical" as const : alertLevel,
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
        simulation: { ...this.state.simulation, enabled: true, machineCount: fleet.filter((item) => item.source === "demo").length },
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

/** Return the process-wide service instance used by all dashboard routes. */
export function getLiveTelemetryService() {
  const globalScope = globalThis as typeof globalThis & { [GLOBAL_KEY]?: LiveTelemetryService };
  if (!globalScope[GLOBAL_KEY]) globalScope[GLOBAL_KEY] = new LiveTelemetryService();
  return globalScope[GLOBAL_KEY];
}
