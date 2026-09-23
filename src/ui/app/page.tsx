"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import RobotScene from "./components/RobotScene";
import { useLiveState } from "../lib/use-live-state";
import { DecisionAction, DashboardState, FEATURE_DEFINITIONS, FleetMachine, TelemetryRecord } from "../lib/types";

const actionLabels: Record<DecisionAction, string> = {
  acknowledge: "Acknowledge",
  inspect: "Send to inspection",
  hold_production: "Hold production",
  schedule_minor_maintenance: "Schedule minor",
  schedule_major_maintenance: "Schedule major",
  urgent_intervention: "Urgent intervention",
  resume_production: "Resume production",
  reset_lifetime: "Restore lifetime",
};

function formatNumber(value: number | undefined, decimals = 1) {
  return value === undefined || !Number.isFinite(value) ? "—" : value.toFixed(decimals);
}

function formatTime(value: string | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Shanghai" }).format(new Date(value));
}

function scoreClass(score: number) {
  return score >= 70 ? "critical" : score >= 40 ? "warning" : "safe";
}

function stateLabel(value: FleetMachine["operationalState"]) {
  return value.replaceAll("_", " ");
}

function StatusDot({ status }: { status: DashboardState["connection"] }) {
  return <span className={`industrial-status-dot ${status}`} aria-hidden="true" />;
}

function MiniTrend({ values }: { values: number[] }) {
  const points = values.length > 1
    ? values.map((value, index) => `${(index / (values.length - 1)) * 100},${100 - value}`).join(" ")
    : "0,80 50,65 100,72";
  return <svg className="fleet-mini-trend" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Urgency trend"><polyline points={points} /></svg>;
}

function UrgencyDial({ score }: { score: number }) {
  return <div className={`industrial-dial ${scoreClass(score)}`} style={{ ["--dial-value" as string]: `${Math.min(score, 100) * 3.6}deg` }}><div><strong>{Math.round(score)}</strong><span>/100</span></div></div>;
}

function TrendChart({ machine }: { machine: FleetMachine | undefined }) {
  const values = machine?.trend ?? [];
  const points = values.length > 1 ? values.map((value, index) => `${(index / (values.length - 1)) * 100},${100 - value}`).join(" ") : "0,80 25,72 55,64 100,68";
  return <div className="industrial-trend"><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Selected machine urgency trajectory"><line x1="0" x2="100" y1="30" y2="30" className="industrial-threshold critical" /><line x1="0" x2="100" y1="60" y2="60" className="industrial-threshold warning" /><polyline points={points} /></svg><span className="trend-axis top">70</span><span className="trend-axis mid">40</span><span className="trend-axis bottom">0</span></div>;
}

function Kpi({ label, value, detail, tone = "" }: { label: string; value: string; detail: string; tone?: string }) {
  return <article className={`industrial-kpi ${tone}`}><span className="industrial-eyebrow">{label}</span><strong>{value}</strong><span>{detail}</span></article>;
}

function FleetCard({ machine, selected, onSelect }: { machine: FleetMachine; selected: boolean; onSelect: () => void }) {
  return <button className={`fleet-card ${selected ? "selected" : ""} ${scoreClass(machine.urgency)}`} type="button" onClick={onSelect}>
    <div className="fleet-card-top"><span className="fleet-index">{machine.stationId.split("-").at(-1)}</span><span className={`state-chip ${machine.operationalState}`}>{stateLabel(machine.operationalState)}</span></div>
    <div className="fleet-card-title"><div><strong>{machine.name}</strong><span>{machine.stationId} · {machine.location}</span></div><span className="fleet-source">{machine.source === "mqtt" ? "MQTT" : "SIM"}</span></div>
    <div className="fleet-card-metrics"><div><span>Urgency</span><strong>{formatNumber(machine.urgency, 0)}</strong></div><div><span>Uncertainty</span><strong>{formatNumber(machine.uncertainty * 100, 0)}%</strong></div><MiniTrend values={machine.trend} /></div>
    <div className="fleet-card-foot"><span className={`risk-pip ${scoreClass(machine.urgency)}`} />{machine.dataQuality === "atypical" ? "Atypical data · review" : machine.humanReview ? "Human review required" : machine.recommendation.replaceAll("_", " ")}<span className="fleet-arrow">↗</span></div>
    <div className="fleet-card-plan"><span>{machine.shiftId} · {machine.piecesRemaining.toLocaleString()} pieces left</span><strong>{machine.lifetimePercent.toFixed(0)}% life</strong></div>
  </button>;
}

function ProductionOrderSetup({ setState }: { setState: (state: DashboardState) => void }) {
  const [targetPieces, setTargetPieces] = useState(100);
  const [productType, setProductType] = useState("Large automotive chassis");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const startProduction = async () => {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/simulation", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "configure_order", targetPieces, productType, shiftLengthMinutes: 480 }) });
      const result = await response.json() as { ok: boolean; state?: DashboardState; error?: string };
      if (!response.ok || !result.state) throw new Error(result.error ?? "Unable to start production order.");
      setState(result.state);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start production order.");
    } finally {
      setBusy(false);
    }
  };
  return <div className="order-setup-backdrop"><section className="order-setup-card" role="dialog" aria-modal="true" aria-labelledby="order-setup-title"><span className="industrial-eyebrow">FIRST RUN / PRODUCTION SETUP</span><h2 id="order-setup-title">Define the production order</h2><p>Set the number of large pieces before the synthetic fleet starts. The scheduler will work in shifts and stop at controlled checkpoints instead of changing the order load abruptly.</p><label htmlFor="order-target">Pieces to produce</label><input id="order-target" type="number" min="1" max="1000000" step="1" value={targetPieces} onChange={(event) => setTargetPieces(Number(event.target.value))} /><label htmlFor="order-product">Product type</label><input id="order-product" value={productType} onChange={(event) => setProductType(event.target.value)} /><div className="order-assumption"><strong>Capacity assumption</strong><span>10 independent cells × 1 piece / 60 s = 0.167 pieces/s fleet · 600 pieces/h nominal.</span><small>Industrial references indicate approximately 46–60 s takt for body-in-white operations; this dashboard value is a configurable simulation assumption.</small></div>{error && <div className="order-error">{error}</div>}<button className="order-start-button" type="button" onClick={() => void startProduction()} disabled={busy || targetPieces < 1}>{busy ? "Starting…" : "Start production"}</button></section></div>;
}

function ProductionOrderPanel({ state, setState }: { state: DashboardState; setState: (state: DashboardState) => void }) {
  const order = state.simulation.productionOrder;
  const [busy, setBusy] = useState(false);
  if (!order) return <ProductionOrderSetup setState={setState} />;
  const progress = order.targetPieces ? Math.min(100, (order.completedPieces / order.targetPieces) * 100) : 0;
  const reset = async () => {
    setBusy(true);
    try {
      const response = await fetch("/api/simulation", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "reset" }) });
      const result = await response.json() as { ok: boolean; state?: DashboardState };
      if (response.ok && result.state) setState(result.state);
    } finally {
      setBusy(false);
    }
  };
  return <section className="production-order-panel industrial-panel"><div><span className="industrial-eyebrow">ACTIVE ORDER / CHECKPOINT SCHEDULER</span><h2>{order.id} · {order.productType}</h2><p>{order.assumption}</p></div><div className="order-progress-block"><strong>{order.completedPieces.toLocaleString()} / {order.targetPieces.toLocaleString()}</strong><div className="order-progress"><span style={{ width: `${progress}%` }} /></div><small>{progress.toFixed(1)}% complete · {order.remainingPieces.toLocaleString()} remaining</small></div><div className="order-facts"><span><b>{order.shiftId}</b> current shift</span><span><b>{order.checkpointEveryPieces.toLocaleString()}</b> piece checkpoint</span><span><b>{state.simulation.checkpointCount}</b> checkpoints passed</span><span><b>{order.fleetPiecesPerSecond.toFixed(3)}</b> pieces/s nominal</span></div><button className="reset-simulation-button" type="button" onClick={() => void reset()} disabled={busy}>{busy ? "Resetting…" : "Reset simulation"}</button></section>;
}

function SensorTable({ current }: { current: TelemetryRecord | null }) {
  return <div className="industrial-sensor-table">{FEATURE_DEFINITIONS.map((definition) => <div className="industrial-sensor-row" key={definition.key}><span>{definition.label}</span><strong>{formatNumber(current?.features[definition.key], definition.decimals)}</strong><small>{definition.unit}</small></div>)}</div>;
}

function DecisionRail({ state, machine, setState }: { state: DashboardState; machine: FleetMachine | undefined; setState: (state: DashboardState) => void }) {
  const [pendingAction, setPendingAction] = useState<DecisionAction | null>(null);
  const [note, setNote] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [scenario, setScenario] = useState("normal");
  if (!machine) return <aside className="decision-rail"><div className="industrial-empty">Waiting for fleet telemetry.</div></aside>;
  const inference = machine.current?.inference;
  const action = pendingAction ? actionLabels[pendingAction] : "";
  const execute = async () => {
    if (!pendingAction) return;
    setBusy(true);
    try {
      const response = await fetch("/api/command", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ deviceId: machine.deviceId, action: pendingAction, operator: "JM", note }) });
      const result = await response.json() as { ok: boolean; state?: DashboardState; error?: string };
      if (!response.ok || !result.state) throw new Error(result.error ?? "Decision was not accepted.");
      setState(result.state);
      setNotice(`${action} accepted · ${result.state.simulation.enabled ? "local simulation" : "MQTT"}`);
      setPendingAction(null);
      setNote("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Decision failed.");
    } finally {
      setBusy(false);
    }
  };
  const request = (next: DecisionAction) => {
    setNotice("");
    setPendingAction(next);
  };
  const publishScenario = async () => {
    setBusy(true);
    try {
      const response = await fetch("/api/scenario", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ deviceId: machine.deviceId, scenario }) });
      const result = await response.json() as { ok: boolean; state?: DashboardState; error?: string };
      if (!response.ok || !result.state) throw new Error(result.error ?? "Scenario was not accepted.");
      setState(result.state);
      setNotice(`Scenario ${scenario} published to ${machine.name}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Scenario command failed.");
    } finally {
      setBusy(false);
    }
  };
  return <aside className="decision-rail" id="decision-rail">
    <div className="decision-heading"><div><span className="industrial-eyebrow">SELECTED ASSET / DECISION GATE</span><h2>{machine.name}</h2><p>{machine.stationId} · {machine.line}</p></div><span className={`state-chip ${machine.operationalState}`}>{stateLabel(machine.operationalState)}</span></div>
    <div className="decision-score"><UrgencyDial score={machine.urgency} /><div><span className="industrial-eyebrow">ADJUSTED URGENCY</span><strong className={scoreClass(machine.urgency)}>{machine.label.toUpperCase()}</strong><p>AI {formatNumber(inference?.predictedUrgency, 1)} · gate {formatNumber(machine.urgency, 1)}</p></div></div>
    <div className="uncertainty-block"><div><span>Model uncertainty</span><strong>{formatNumber(machine.uncertainty * 100, 0)}%</strong></div><div className="uncertainty-track"><span style={{ width: `${Math.min(100, machine.uncertainty * 100)}%` }} /></div><small>{machine.humanReview ? "Above review threshold · operator decision required" : "Below review threshold · monitor"}</small></div>
    <div className="production-plan"><span className="industrial-eyebrow">SCHEDULING / BOUNDED WORK</span><strong>{machine.productionPlan.action === "stop_and_review" ? "Stop and request human review" : machine.productionPlan.action === "reduce_load" ? `Max ${machine.productionPlan.maxAdditionalPieces.toLocaleString()} additional pieces` : `Continue up to ${machine.productionPlan.maxAdditionalPieces.toLocaleString()} pieces`}</strong><small>Re-evaluate every {machine.productionPlan.reevaluateEveryPieces.toLocaleString()} pieces · {machine.piecesRemaining.toLocaleString()} remaining in {machine.shiftId}</small><small>Robot lifetime {machine.lifetimePercent.toFixed(0)}% · {machine.maintenanceCount} maintenance cycles · service wear {(machine.serviceWear * 100).toFixed(0)}%</small></div>
    <div className={`review-callout ${machine.humanReview ? "attention" : "clear"}`}><span className="review-symbol">{machine.humanReview ? "!" : "✓"}</span><div><strong>{machine.humanReview ? "Human review required" : "Selective gate clear"}</strong><span>{inference?.qualityFlags.join(" · ") || "No quality flags on the latest frame."}</span></div></div>
    <div className="recommendation-block"><span className="industrial-eyebrow">MODEL RECOMMENDATION</span><strong>{machine.recommendation.replaceAll("_", " ")}</strong><p>Use the machine context, uncertainty and latest process signals before confirming.</p></div>
    <div className="scenario-command"><span className="industrial-eyebrow">ESP32 SCENARIO COMMAND</span><div><select value={scenario} onChange={(event) => setScenario(event.target.value)}><option value="normal">Normal</option><option value="low_shielding_gas">Low shielding gas</option><option value="lens_contamination">Lens contamination</option><option value="focal_offset">Focal offset</option><option value="fixture_vibration">Fixture vibration</option><option value="high_laser_power">High laser power</option></select><button type="button" onClick={publishScenario} disabled={busy || machine.source !== "mqtt"}>Publish</button></div><small>Available for the MQTT-connected robot only.</small></div>
    <div className="decision-actions"><div className="decision-actions-label">Operator actions</div><div className="decision-button-grid"><button type="button" onClick={() => request("inspect")}>Inspect</button><button type="button" onClick={() => request("acknowledge")}>Acknowledge</button><button type="button" className="amber" onClick={() => request("hold_production")}>Hold production</button><button type="button" onClick={() => request("schedule_minor_maintenance")}>Schedule minor</button><button type="button" className="amber" onClick={() => request("schedule_major_maintenance")}>Schedule major</button><button type="button" className="red" onClick={() => request("urgent_intervention")}>Urgent intervention</button><button type="button" className="full" onClick={() => request("resume_production")}>Resume production</button><button type="button" className="full lifetime-action" onClick={() => request("reset_lifetime")}>Restore robot / ESP32 lifetime to 100%</button></div></div>
    {pendingAction && <div className="decision-confirm"><span className="industrial-eyebrow">CONFIRM HUMAN DECISION</span><strong>{action} · {machine.name}</strong><textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Operator note / reason" rows={2} /><div><button type="button" className="confirm" onClick={execute} disabled={busy}>{busy ? "Publishing…" : "Confirm action"}</button><button type="button" className="quiet" onClick={() => setPendingAction(null)}>Cancel</button></div></div>}
    {notice && <div className="decision-notice">{notice}</div>}
    <div className="decision-disclaimer">Commands are simulated locally when MQTT is unavailable. Calibrated live machine control is not enabled in this research build.</div>
  </aside>;
}

export default function DashboardPage() {
  const { state, setState, streamStatus } = useLiveState();
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  useEffect(() => {
    if (state && (!selectedDeviceId || !state.fleet.some((machine) => machine.deviceId === selectedDeviceId))) setSelectedDeviceId(state.selectedDeviceId || state.fleet[0]?.deviceId || "");
  }, [state, selectedDeviceId]);
  const orderedFleet = useMemo(() => [...(state?.fleet ?? [])].sort((a, b) => b.urgency - a.urgency), [state?.fleet]);
  const machine = orderedFleet.find((item) => item.deviceId === selectedDeviceId) ?? orderedFleet[0];
  const reviewQueue = state?.modelTelemetry.reviewQueue ?? 0;
  const producing = state?.fleet.filter((item) => item.operationalState === "production").length ?? 0;
  const selectedCurrent = machine?.current ?? null;
  const latestEvents = useMemo(() => (state?.alerts ?? []).slice(0, 6), [state?.alerts]);

  if (!state) return <main className="industrial-loading"><div className="loading-orbit" /><span>Opening ORCHESTRA control room…</span></main>;
  return <main className="industrial-shell">
    <aside className="industrial-sidebar"><Link className="industrial-brand" href="/"><span>O</span><div><strong>ORCHESTRA</strong><small>industrial intelligence</small></div></Link><div className="sidebar-divider" /><span className="industrial-nav-label">COMMAND SYSTEM</span><nav className="industrial-nav"><Link className="active" href="/"><span>01</span>Operations</Link><Link href="/models"><span>02</span>Model laboratory</Link><a href="#audit"><span>03</span>Audit trail</a></nav><div className="sidebar-context"><span className="industrial-eyebrow">PILOT CONTEXT</span><strong>CN / EAST ASIA</strong><span>10 laser welding cells</span><span className="sidebar-context-line"><i />Edge-first · operator-aware</span></div><div className="sidebar-foot">Synthetic lab feed<br />Simulation evidence boundary</div></aside>
    <section className="industrial-content"><header className="industrial-topbar"><div><span className="industrial-breadcrumb">ORCHESTRA / OPERATIONS / <em>FLEET COMMAND</em></span><h1>Production intelligence</h1><p>Human-in-the-loop control for a 10-cell laser-welding fleet.</p></div><div className="industrial-top-actions"><span className="simulation-pill"><i />{state.simulation.label}</span><span className="connection-pill industrial-connection"><StatusDot status={state.connection} />{state.connection === "mqtt" ? "MQTT / ESP32" : state.connection === "degraded" ? "MQTT degraded" : "Synthetic telemetry"}<small>{streamStatus}</small></span><button className="top-reset-button" type="button" onClick={() => void fetch("/api/simulation", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "reset" }) }).then((response) => response.json()).then((result: { state?: DashboardState }) => result.state && setState(result.state))}>Reset simulation</button><span className="operator-avatar">JM</span></div></header>
      <div className="industrial-command-strip"><div><span className="industrial-eyebrow">CONTROL ROOM / {state.station.location}</span><strong>{state.station.line}</strong><span>Decision support · no automatic stop authority</span></div><div className="command-strip-meta"><span><StatusDot status={state.connection} />{state.totals.messages} frames accepted</span><span>Last update {formatTime(state.updatedAt)}</span></div></div>
      <ProductionOrderPanel state={state} setState={setState} />
      <section className="industrial-kpi-grid"><Kpi label="Fleet coverage" value={`${state.fleet.length} / 10`} detail="cells reporting" /><Kpi label="Producing" value={String(producing)} detail={`${state.fleet.length - producing} outside production`} tone={producing < state.fleet.length ? "warning" : ""} /><Kpi label="Review queue" value={String(reviewQueue)} detail="uncertainty / urgency gate" tone={reviewQueue ? "critical" : ""} /><Kpi label="Frames / minute" value={String(state.modelTelemetry.framesPerMinute)} detail={`${state.totals.mqttMessages} from MQTT`} /><Kpi label="Fleet urgency" value={formatNumber(state.modelTelemetry.averageUrgency, 0)} detail={`avg · ${state.modelTelemetry.highRiskMachines} high risk`} tone={scoreClass(state.modelTelemetry.averageUrgency)} /></section>
      <section className="fleet-command-layout"><div className="fleet-zone"><div className="section-heading"><div><span className="industrial-eyebrow">FLEET BOARD / 10 ASSETS</span><h2>Operational posture</h2></div><span className="section-meta"><i />Sorted by maintenance urgency · 17 features / cell</span></div><div className="fleet-grid">{orderedFleet.map((item) => <FleetCard key={item.deviceId} machine={item} selected={machine?.deviceId === item.deviceId} onSelect={() => setSelectedDeviceId(item.deviceId)} />)}</div></div><DecisionRail state={state} machine={machine} setState={setState} /></section>
      <section className="industrial-lower-grid"><article className="industrial-panel selected-asset-panel"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">SELECTED ASSET / PROCESS VIEW</span><h2>{machine?.name ?? "Waiting"}</h2><p>{machine?.location} · {machine?.line}</p></div><span className="asset-live-label"><StatusDot status={state.connection} />{selectedCurrent?.source === "mqtt" ? "MQTT live" : "synthetic"}</span></div><RobotScene /><div className="asset-meta-grid"><div><span>Asset</span><strong>{machine?.asset ?? "—"}</strong></div><div><span>Scenario</span><strong>{machine?.scenario ?? "—"}</strong></div><div><span>Last frame</span><strong>{formatTime(selectedCurrent?.timestamp)}</strong></div><div><span>Gateway</span><strong>{selectedCurrent?.deviceId ?? "waiting"}</strong></div></div></article><article className="industrial-panel telemetry-panel"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">TELEMETRY CONTRACT / ALL FIELDS</span><h2>Process signals</h2></div><span className="schema-badge">17 FEATURES</span></div><SensorTable current={selectedCurrent} /><div className="telemetry-note"><span>Schema validation active</span><strong>{selectedCurrent?.inference.qualityFlags.length ? selectedCurrent.inference.qualityFlags.join(" · ") : "No active quality flags"}</strong></div></article><article className="industrial-panel trend-panel-new"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">SELECTED ASSET / LAST 16 FRAMES</span><h2>Urgency trajectory</h2></div><span className={`risk-label ${scoreClass(machine?.urgency ?? 0)}`}>{formatNumber(machine?.urgency, 0)} / 100</span></div><TrendChart machine={machine} /><div className="trend-footer-new"><span>Latest {formatTime(machine?.lastSeen)}</span><span>Review gate {formatNumber((machine?.uncertainty ?? 0) * 100, 0)}%</span></div></article><article className="industrial-panel event-panel" id="audit"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">AUDIT / FEEDBACK LOOP</span><h2>Recent events</h2></div><Link href="/models#audit">Full audit ↗</Link></div><div className="industrial-events">{latestEvents.map((event) => <div className="industrial-event" key={event.id}><i className={event.level} /><div><strong>{event.title}</strong><span>{event.detail}</span></div><time>{formatTime(event.timestamp)}</time></div>)}{!latestEvents.length && <div className="industrial-empty">No events yet.</div>}</div>{state.decisions.slice(0, 2).map((decision) => <div className="decision-log" key={decision.id}><span>OPERATOR · {decision.operator}</span><strong>{actionLabels[decision.action]}</strong><small>{decision.machineName} · {decision.transport}</small></div>)}</article></section>
      <footer className="industrial-footer"><span>ORCHESTRA / research control room</span><span>Simulation only · no safety certification · no automatic machine stop</span></footer>
    </section>
  </main>;
}
