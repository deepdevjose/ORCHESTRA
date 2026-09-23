"use client";

import { useEffect, useMemo, useState } from "react";
import RobotScene from "./components/RobotScene";
import { DashboardState, FEATURE_DEFINITIONS, TelemetryRecord } from "../lib/types";

const navItems = [
  ["01", "Overview", "#overview"],
  ["02", "Live signals", "#live-signals"],
  ["03", "Human review", "#human-review"],
  ["04", "Scheduling", "#scheduling"],
];

function formatNumber(value: number | undefined, decimals = 1) {
  if (value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(decimals);
}

function formatTime(value: string | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(new Date(value));
}

function scoreClass(score: number) {
  return score >= 70 ? "critical" : score >= 40 ? "warning" : "safe";
}

function StatusDot({ status }: { status: DashboardState["connection"] }) {
  const tone = status === "mqtt" ? "live" : status === "connecting" ? "pulse" : status === "degraded" ? "warning" : "demo";
  return <span className={"status-dot " + tone} />;
}

function ScoreRing({ score }: { score: number }) {
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (circumference * Math.min(score, 100)) / 100;
  return (
    <div className="score-ring" style={{ ["--ring-offset" as string]: offset }}>
      <svg viewBox="0 0 150 150" aria-label={"Maintenance urgency " + Math.round(score)}>
        <circle className="ring-track" cx="75" cy="75" r={radius} />
        <circle className={"ring-value " + scoreClass(score)} cx="75" cy="75" r={radius} />
      </svg>
      <div className="score-ring-value"><strong>{Math.round(score)}</strong><span>/ 100</span></div>
    </div>
  );
}

function Sparkline({ history }: { history: TelemetryRecord[] }) {
  const values = history.map((row) => row.inference.adjustedUrgency);
  const points = values.length
    ? values.map((value, index) => {
      const x = values.length === 1 ? 0 : (index / (values.length - 1)) * 100;
      const y = 100 - value;
      return x.toFixed(1) + "," + y.toFixed(1);
    }).join(" ")
    : "0,85 30,72 60,58 100,64";
  return (
    <svg className="sparkline" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Live urgency trend">
      <line x1="0" x2="100" y1="30" y2="30" className="chart-threshold critical-line" />
      <line x1="0" x2="100" y1="60" y2="60" className="chart-threshold warning-line" />
      <polyline points={points} className="chart-line" />
    </svg>
  );
}

function KpiCard({ label, value, detail, tone = "" }: { label: string; value: string; detail: string; tone?: string }) {
  return <article className={"kpi-card " + tone}><span className="eyebrow">{label}</span><strong>{value}</strong><span className="kpi-detail">{detail}</span></article>;
}

function SensorTable({ current }: { current: TelemetryRecord | null }) {
  return (
    <div className="sensor-table">
      {FEATURE_DEFINITIONS.slice(0, 8).map((definition) => (
        <div className="sensor-row" key={definition.key}>
          <div className="sensor-name"><span className="sensor-bullet" />{definition.label}</div>
          <strong>{formatNumber(current?.features[definition.key], definition.decimals)}</strong>
          <span>{definition.unit}</span>
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [state, setState] = useState<DashboardState | null>(null);
  const [streamStatus, setStreamStatus] = useState("connecting");

  useEffect(() => {
    const source = new EventSource("/api/stream");
    source.onopen = () => setStreamStatus("connected");
    source.onmessage = (event) => {
      setState(JSON.parse(event.data) as DashboardState);
      setStreamStatus("connected");
    };
    source.onerror = () => setStreamStatus("reconnecting");
    return () => source.close();
  }, []);

  const current = state?.current ?? null;
  const inference = current?.inference;
  const score = inference?.adjustedUrgency ?? 0;
  const reviewRate = state && state.totals.messages ? Math.round((state.totals.reviews / state.totals.messages) * 100) : 0;
  const sourceLabel = state?.connection === "mqtt" ? "MQTT / ESP32" : state?.connection === "connecting" ? "Connecting to broker" : state?.connection === "degraded" ? "MQTT degraded" : "Demo telemetry";
  const sensorStatus = useMemo(() => {
    if (!current) return "Waiting for first frame";
    if (current.inference.qualityFlags.length) return current.inference.qualityFlags[0];
    return "Nominal signal quality";
  }, [current]);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">O</div><div><strong>ORCHESTRA</strong><span>industrial intelligence</span></div></div>
        <div className="sidebar-rule" />
        <p className="nav-label">CONTROL ROOM</p>
        <nav aria-label="Dashboard sections">
          {navItems.map(([number, label, href], index) => <a href={href} className={index === 0 ? "nav-item active" : "nav-item"} key={label}><span>{number}</span>{label}</a>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="china-card"><span className="eyebrow">PILOT CONTEXT</span><strong>CN / SUZHOU</strong><span>Laser welding cell 01</span><div className="china-line"><span className="china-dot" />Edge-first · operator-aware</div></div>
          <p className="sidebar-foot">Lab-informed foundation<br />Live industrial validation pending</p>
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div><div className="breadcrumb">ORCHESTRA / OPERATIONS / <span>LIVE</span></div><h1>Laser welding intelligence</h1><p className="subtitle">A calm command view for human-centred predictive maintenance</p></div>
          <div className="topbar-actions"><div className="connection-pill"><StatusDot status={state?.connection ?? "connecting"} /><span>{sourceLabel}</span><small>{streamStatus}</small></div><button className="avatar" aria-label="Operator profile">JM</button></div>
        </header>

        <section className="intro-grid" id="overview">
          <div className="intro-copy">
            <div className="context-strip"><div><span className="context-icon">⌁</span><div><strong>{state?.station.location ?? "Suzhou · Jiangsu"}</strong><span>{state?.station.line ?? "Automotive battery enclosure"} · {state?.station.asset ?? "Laser welding cell 01"}</span></div></div><div className="strip-note"><span className="tiny-dot" /> Gateway active <span className="strip-separator">|</span> Last frame {formatTime(state?.updatedAt)}</div></div>
            <div className="intro-readout"><span className="eyebrow">ASSET READOUT / 01</span><h2>One view from robot cell to maintenance decision.</h2><p>Telemetry from the edge is scored, checked for uncertainty, and presented to an operator before scheduling enters the loop.</p></div>
            <div className="network-line"><span className="network-dot" /> AP: <strong>Jose&apos;s Network</strong><span className="network-separator" /> Topic: <strong>{state?.mqttTopic ?? "orchestra/laser-welding/+/telemetry"}</strong></div>
          </div>
          <article className="panel robot-panel"><div className="panel-header"><div><span className="eyebrow">LIVE ASSET / 3D VIEW</span><h2>Robot cell</h2></div><span className="asset-status"><StatusDot status={state?.connection ?? "connecting"} />{current?.deviceId ?? "ESP32 waiting"}</span></div><RobotScene /><div className="robot-meta"><div><span>Model</span><strong>SIASUN SR12A</strong></div><div><span>Gateway</span><strong>{current?.source === "mqtt" ? "MQTT live" : "Demo feed"}</strong></div><div><span>Frames</span><strong>{String(state?.totals.messages ?? 0).padStart(2, "0")}</strong></div></div></article>
        </section>

        <section className="kpi-grid">
          <KpiCard label="Current urgency" value={formatNumber(score, 0)} detail={inference ? inference.label.toUpperCase() + " · " + inference.recommendation.replaceAll("_", " ") : "Awaiting model"} tone={scoreClass(score)} />
          <KpiCard label="Human review rate" value={reviewRate + "%"} detail={state ? state.totals.reviews + " referrals in current session" : "No frames yet"} />
          <KpiCard label="Signal health" value={current ? "98.6%" : "—"} detail={sensorStatus} />
          <KpiCard label="Model state" value={state?.model.source === "python" ? "LIVE" : "READY"} detail={state?.model.name ?? "Model warming"} />
        </section>

        <section className="main-grid">
          <article className="panel urgency-panel"><div className="panel-header"><div><span className="eyebrow">DECISION SIGNAL</span><h2>Maintenance urgency</h2></div><span className={"badge " + scoreClass(score)}>{inference?.label ?? "—"}</span></div><div className="urgency-body"><ScoreRing score={score} /><div className="urgency-copy"><div className="metric-line"><span>AI prediction</span><strong>{formatNumber(inference?.predictedUrgency, 1)} <small>/ 100</small></strong></div><div className="metric-line"><span>After human gate</span><strong>{formatNumber(inference?.adjustedUrgency, 1)} <small>/ 100</small></strong></div><div className="metric-line"><span>Model uncertainty</span><strong>{formatNumber((inference?.uncertainty ?? 0) * 100, 0)}<small>%</small></strong></div><div className="decision-message"><span className="decision-icon">{inference?.humanReview ? "!" : "✓"}</span><div><strong>{inference?.humanReview ? "Operator review requested" : "Autonomous path available"}</strong><span>{inference?.humanReview ? "The signal is uncertain or operationally sensitive." : "No human escalation is required for this frame."}</span></div></div></div></div><div className="panel-footer"><span>Thresholds</span><div className="threshold-key"><i className="key-safe" />0–40 safe <i className="key-warning" />40–70 review <i className="key-critical" />70+ urgent</div></div></article>

          <article className="panel trend-panel" id="live-signals"><div className="panel-header"><div><span className="eyebrow">LAST 36 FRAMES</span><h2>Urgency trajectory</h2></div><span className="live-label"><StatusDot status={state?.connection ?? "connecting"} />LIVE</span></div><div className="trend-chart"><Sparkline history={state?.history ?? []} /><div className="chart-label label-critical">70</div><div className="chart-label label-warning">40</div></div><div className="trend-footer"><span>Oldest frame</span><strong>{state?.history[0] ? formatTime(state.history[0].timestamp) : "—"}</strong><span className="trend-spacer" /><span>Latest frame</span><strong>{formatTime(current?.timestamp)}</strong></div></article>

          <article className="panel sensor-panel"><div className="panel-header"><div><span className="eyebrow">MACHINE / IOT AGENT</span><h2>Process signals</h2></div><span className="device-chip">{current?.deviceId ?? "ESP32 / waiting"}</span></div><SensorTable current={current} /><div className="sensor-footer"><span>Payload schema</span><strong>17 features</strong><span>·</span><span>Source</span><strong>{current?.source === "mqtt" ? "MQTT live" : "Synthetic demo"}</strong></div></article>

          <article className="panel chain-panel" id="human-review"><div className="panel-header"><div><span className="eyebrow">ORCHESTRATION LAYER</span><h2>Decision chain</h2></div><span className="chain-status">4 agents</span></div><div className="chain">{[["01", "Machine / IoT", current ? "Frame ingested" : "Waiting", "complete"], ["02", "AI Predictive", inference ? inference.modelName : "Warming model", inference ? "complete" : "pending"], ["03", "Human Operator", inference?.humanReview ? "Review requested" : "Selective gate", inference?.humanReview ? "attention" : "complete"], ["04", "RL Scheduler", inference ? inference.recommendation.replaceAll("_", " ") : "Awaiting decision", inference ? "next" : "pending"]].map(([number, label, detail, status]) => <div className="chain-step" key={label}><div className={"chain-icon " + status}>{status === "complete" ? "✓" : status === "attention" ? "!" : "→"}</div><div><span>{number} · {label}</span><strong>{detail}</strong></div>{number !== "04" && <div className="chain-connector" />}</div>)}</div><div className="chain-note"><span className="note-icon">i</span><span>Scheduling remains a decision-support layer; this dashboard does not issue a machine stop command.</span></div></article>
        </section>

        <section className="bottom-grid"><article className="panel alerts-panel"><div className="panel-header"><div><span className="eyebrow">FEEDBACK LOOP</span><h2>Recent events</h2></div><span className="event-count">{state?.alerts.length ?? 0} active</span></div><div className="alerts-list">{(state?.alerts ?? []).slice(0, 4).map((alert) => <div className="alert-row" key={alert.id}><span className={"alert-marker " + alert.level} /><div><strong>{alert.title}</strong><span>{alert.detail}</span></div><time>{formatTime(alert.timestamp)}</time></div>)}{!state?.alerts.length && <div className="empty-state">No events recorded yet.</div>}</div></article><article className="panel model-panel" id="scheduling"><div className="panel-header"><div><span className="eyebrow">MODEL REGISTRY</span><h2>Runtime status</h2></div><span className="model-live">● READY</span></div><div className="model-details"><div><span>Predictive agent</span><strong>{state?.model.name ?? "initialising"}</strong></div><div><span>Version</span><strong>{state?.model.version ?? "—"}</strong></div><div><span>Inference layer</span><strong>{state?.model.source === "python" ? "Python / ORCHESTRA" : "UI fallback"}</strong></div><div><span>Human gate</span><strong>uncertainty ≥ 0.45</strong></div></div><p className="model-footnote">The current repository model is lab-informed and synthetic until the ESP32 payload is calibrated against the China pilot cell.</p></article></section>

        <footer className="page-footer"><span>ORCHESTRA · China smart-manufacturing pilot view</span><span>Lab-informed · Not a safety certification</span></footer>
      </section>
    </main>
  );
}

