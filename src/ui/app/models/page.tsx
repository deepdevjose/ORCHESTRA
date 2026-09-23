"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useLiveState } from "../../lib/use-live-state";
import { DashboardState, FleetMachine } from "../../lib/types";

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

function LabKpi({ label, value, detail, tone = "" }: { label: string; value: string; detail: string; tone?: string }) {
  return <article className={`industrial-kpi ${tone}`}><span className="industrial-eyebrow">{label}</span><strong>{value}</strong><span>{detail}</span></article>;
}

function ModelCard({ eyebrow, name, version, status, detail, tone = "" }: { eyebrow: string; name: string; version: string; status: string; detail: string; tone?: string }) {
  return <article className={`model-registry-card ${tone}`}><div className="model-registry-top"><span className="industrial-eyebrow">{eyebrow}</span><span className="model-status"><i />{status}</span></div><h3>{name}</h3><span className="model-version">{version}</span><p>{detail}</p></article>;
}

function FleetModelRow({ machine }: { machine: FleetMachine }) {
  return <div className="model-matrix-row"><div className="matrix-machine"><span className={`risk-pip ${scoreClass(machine.urgency)}`} /><div><strong>{machine.name}</strong><span>{machine.deviceId} · {machine.scenario}</span></div></div><strong>{formatNumber(machine.current?.inference.predictedUrgency, 1)}</strong><strong className={scoreClass(machine.urgency)}>{formatNumber(machine.urgency, 1)}</strong><strong>{formatNumber(machine.uncertainty * 100, 0)}%</strong><span className={machine.humanReview ? "matrix-review" : "matrix-clear"}>{machine.humanReview ? "Review" : "Clear"}</span><span className={`matrix-state ${machine.operationalState}`}>{stateLabel(machine.operationalState)}</span></div>;
}

export default function ModelsPage() {
  const { state, streamStatus } = useLiveState();
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  useEffect(() => {
    if (state && (!selectedDeviceId || !state.fleet.some((machine) => machine.deviceId === selectedDeviceId))) {
      setSelectedDeviceId(state.selectedDeviceId || state.fleet[0]?.deviceId || "");
    }
  }, [state, selectedDeviceId]);
  const selectedMachine = state?.fleet.find((machine) => machine.deviceId === selectedDeviceId) ?? state?.fleet[0];
  const history = (state?.history ?? []).filter((record) => record.deviceId === selectedMachine?.deviceId);
  const chartRows = history.slice(-40);
  const urgencyPoints = chartRows.length > 1 ? chartRows.map((row, index) => `${(index / (chartRows.length - 1)) * 100},${100 - row.inference.adjustedUrgency}`).join(" ") : "0,78 20,64 48,70 76,43 100,58";
  const uncertaintyPoints = chartRows.length > 1 ? chartRows.map((row, index) => `${(index / (chartRows.length - 1)) * 100},${100 - row.inference.uncertainty * 100}`).join(" ") : "0,82 20,70 48,75 76,48 100,61";
  const highestRisk = useMemo(() => [...(state?.fleet ?? [])].sort((a, b) => b.urgency - a.urgency).slice(0, 5), [state?.fleet]);
  if (!state) return <main className="industrial-loading"><div className="loading-orbit" /><span>Opening model laboratory…</span></main>;
  return <main className="industrial-shell">
    <aside className="industrial-sidebar"><Link className="industrial-brand" href="/"><span>O</span><div><strong>ORCHESTRA</strong><small>industrial intelligence</small></div></Link><div className="sidebar-divider" /><span className="industrial-nav-label">COMMAND SYSTEM</span><nav className="industrial-nav"><Link href="/"><span>01</span>Operations</Link><Link className="active" href="/models"><span>02</span>Model laboratory</Link><a href="#audit"><span>03</span>Audit trail</a></nav><div className="sidebar-context"><span className="industrial-eyebrow">EXPERIMENTAL CONTEXT</span><strong>MODEL OBSERVATORY</strong><span>10 synthetic machine streams</span><span className="sidebar-context-line"><i />Traceable · inspectable · provisional</span></div><div className="sidebar-foot">Synthetic lab feed<br />Statistical validation pending</div></aside>
    <section className="industrial-content"><header className="industrial-topbar"><div><span className="industrial-breadcrumb">ORCHESTRA / MODEL LABORATORY / <em>EXPERIMENTAL</em></span><h1>Model observatory</h1><p>Inspecting how telemetry enters the inference and human-review loop.</p></div><div className="industrial-top-actions"><span className="simulation-pill"><i />EXPERIMENTAL / SYNTHETIC</span><span className="connection-pill industrial-connection"><StatusDot status={state.connection} />{state.connection === "mqtt" ? "MQTT / ESP32" : "Synthetic telemetry"}<small>{streamStatus}</small></span><span className="operator-avatar">JM</span></div></header>
      <div className="industrial-command-strip model-strip"><div><span className="industrial-eyebrow">DATA PLANE / LIVE OBSERVATION</span><strong>{state.model.name} · {state.model.version}</strong><span>Fallback is expected when the Python model service is unavailable.</span></div><div className="command-strip-meta model-selector"><label htmlFor="model-robot">Robot</label><select id="model-robot" value={selectedMachine?.deviceId ?? ""} onChange={(event) => setSelectedDeviceId(event.target.value)}>{state.fleet.map((machine) => <option key={machine.deviceId} value={machine.deviceId}>{machine.name} · {machine.source === "mqtt" ? "MQTT" : "SIM"}</option>)}</select><span><StatusDot status={state.connection} />{state.totals.messages} accepted frames</span></div></div>
      <section className="industrial-kpi-grid model-kpis"><LabKpi label="Frames / minute" value={String(state.modelTelemetry.framesPerMinute)} detail="ingestion rate" /><LabKpi label="Average urgency" value={formatNumber(state.modelTelemetry.averageUrgency, 1)} detail="fleet adjusted score" tone={scoreClass(state.modelTelemetry.averageUrgency)} /><LabKpi label="Average uncertainty" value={`${formatNumber(state.modelTelemetry.averageUncertainty * 100, 0)}%`} detail="model confidence gate" tone={state.modelTelemetry.averageUncertainty >= 0.45 ? "critical" : ""} /><LabKpi label="Review queue" value={String(state.modelTelemetry.reviewQueue)} detail="awaiting operator" tone={state.modelTelemetry.reviewQueue ? "warning" : ""} /><LabKpi label="Human decisions" value={String(state.decisions.length)} detail="session audit records" /></section>
      <section className="model-registry-grid"><ModelCard eyebrow="INFERENCE / PRIMARY" name={state.model.name} version={state.model.version} status={state.model.source === "python" ? "PYTHON SERVICE" : "UI FALLBACK"} detail="Maps the 17-feature process frame to predicted urgency, process instability, recommendation and quality flags." tone={state.model.source === "fallback" ? "warning" : ""} /><ModelCard eyebrow="GOVERNANCE / GATE" name="Uncertainty gate" version="threshold 0.45" status="ACTIVE" detail="Escalates uncertain or high-urgency frames to the operator instead of treating the prediction as an autonomous command." /><ModelCard eyebrow="POLICY / NEXT STEP" name="Maintenance policy" version="human v0.1" status="DECISION SUPPORT" detail="Turns the model output into inspect, hold, schedule or urgent-intervention options. The operator confirms every action." /></section>
      <section className="model-observatory-grid"><article className="industrial-panel model-chart-panel"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">SIGNAL TRACE / {selectedMachine?.name ?? "SELECTED ROBOT"}</span><h2>Urgency vs. uncertainty</h2></div><span className="chart-legend"><i className="urgency" />Urgency <i className="uncertainty" />Uncertainty</span></div><div className="model-chart"><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Urgency and uncertainty traces"><line x1="0" x2="100" y1="30" y2="30" className="industrial-threshold critical" /><line x1="0" x2="100" y1="60" y2="60" className="industrial-threshold warning" /><polyline className="urgency-line" points={urgencyPoints} /><polyline className="uncertainty-line" points={uncertaintyPoints} /></svg><span>0</span><span>40</span><span>70</span><span>100</span></div><div className="chart-footnote">Each frame is tagged with source, model version and review outcome. This trace is an experimental observability view, not a validation curve.</div></article><article className="industrial-panel model-events-panel"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">MODEL EVENTS / {selectedMachine?.name ?? "SELECTED ROBOT"}</span><h2>Gate activity</h2></div><span className="schema-badge">LIVE</span></div><div className="industrial-events">{state.modelTelemetry.modelEvents.filter((event) => event.deviceId === selectedMachine?.deviceId).slice(0, 8).map((event) => <div className="industrial-event" key={event.id}><i className={event.level} /><div><strong>{event.event}</strong><span>{event.detail} · {event.deviceId}</span></div><time>{formatTime(event.timestamp)}</time></div>)}{!state.modelTelemetry.modelEvents.some((event) => event.deviceId === selectedMachine?.deviceId) && <div className="industrial-empty">No model events for this robot yet.</div>}</div></article></section>
      <section className="industrial-panel model-matrix-panel"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">FLEET MODEL MATRIX / {state.fleet.length} CELLS</span><h2>What the models are seeing</h2></div><span className="section-meta">Sorted by current urgency</span></div><div className="model-matrix-head"><span>Machine</span><span>Predicted</span><span>Adjusted</span><span>Uncertainty</span><span>Gate</span><span>Operational state</span></div>{highestRisk.map((machine) => <FleetModelRow key={machine.deviceId} machine={machine} />)}</section>
      <section className="model-audit-layout" id="audit"><article className="industrial-panel bar-panel"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">RISK DISTRIBUTION</span><h2>Fleet comparison</h2></div><span className="section-meta">Adjusted urgency / uncertainty</span></div><div className="model-bars">{state.fleet.map((machine) => <div className="model-bar-row" key={machine.deviceId}><span>{machine.name.replace("Cell ", "C")}</span><div><i className={`urgency-bar ${scoreClass(machine.urgency)}`} style={{ width: `${Math.min(100, machine.urgency)}%` }} /><i className="uncertainty-bar" style={{ width: `${Math.min(100, machine.uncertainty * 100)}%` }} /></div><strong>{formatNumber(machine.urgency, 0)}</strong></div>)}</div></article><article className="industrial-panel audit-panel"><div className="industrial-panel-heading"><div><span className="industrial-eyebrow">OPERATOR AUDIT / APPEND-ONLY SESSION VIEW</span><h2>Human decisions</h2></div><Link href="/">Operations ↗</Link></div><div className="audit-list">{state.decisions.map((decision) => <div className="audit-row" key={decision.id}><div><strong>{decision.action.replaceAll("_", " ")}</strong><span>{decision.machineName} · {decision.operator}</span></div><span className="audit-transport">{decision.transport}</span><time>{formatTime(decision.timestamp)}</time><small>{decision.note}</small></div>)}{!state.decisions.length && <div className="industrial-empty">No operator decisions in this session.</div>}</div></article></section>
      <footer className="industrial-footer"><span>ORCHESTRA / experimental model laboratory</span><span>Provisional synthetic evidence · calibration and external validation pending</span></footer>
    </section>
  </main>;
}
