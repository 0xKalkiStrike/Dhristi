import type { LiveEvent } from "../types";
import { ConfidenceBadge, EmptyState, LiveDot } from "./ui";
import { eventLabel } from "./ui";

function timeOf(ts?: string) {
  if (!ts) return "";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? "" : d.toLocaleTimeString();
}

function EventRow({ e }: { e: LiveEvent }) {
  const time = timeOf(e.timestamp);
  if (e.type === "speed_event") {
    return (
      <Row time={time} cam={e.camera_id} tone={e.is_violation ? "crit" : "accent"}
        title={e.is_violation ? "OVERSPEED" : "SPEED"} conf={e.confidence}>
        <span className="font-mono text-white">{e.plate || e.tracking_id}</span>
        <span className={`font-mono ${e.is_violation ? "text-cmd-crit" : "text-cmd-text"}`}>
          {Math.round(e.speed_kmh)} km/h
        </span>
        <span className="text-cmd-muted">limit {e.limit}</span>
      </Row>
    );
  }
  if (e.type === "traffic_event") {
    return (
      <Row time={time} cam={e.camera_id} tone={e.severity === "critical" ? "crit" : e.severity === "warning" ? "warn" : "accent"}
        title={eventLabel(e.event_type)} conf={e.confidence}>
        <span className="text-cmd-text text-[11px] leading-tight">{e.reason}</span>
      </Row>
    );
  }
  if (e.type === "plate_detected") {
    return (
      <Row time={time} cam={e.camera_id} tone="accent" title="ANPR" conf={e.confidence}>
        <span className="font-mono text-white tracking-wider">{e.plate}</span>
        {e.needs_verification && <span className="text-cmd-warn text-[10px]">verify</span>}
      </Row>
    );
  }
  if (e.type === "vehicle_detected") {
    return (
      <Row time={time} cam={e.camera_id} tone="muted" title="DETECT">
        <span className="text-cmd-muted">{e.count} vehicle(s)</span>
      </Row>
    );
  }
  if (e.type === "vehicle_updated") {
    return (
      <Row time={time} cam={e.camera_id} tone="muted" title="TRACK">
        <span className="font-mono text-cmd-text">{e.vehicle_class}</span>
        <span className="text-cmd-muted">{e.color}</span>
      </Row>
    );
  }
  if (e.type === "camera_status") {
    return (
      <Row time={time} cam={e.camera_id} tone="muted" title="CAMERA">
        <span className="text-cmd-muted">{e.status}{e.environment ? ` · ${e.environment}` : ""}</span>
      </Row>
    );
  }
  return null;
}

function Row({
  time, cam, title, tone, conf, children,
}: {
  time: string; cam?: string; title: string; conf?: number;
  tone: "crit" | "warn" | "accent" | "muted"; children: React.ReactNode;
}) {
  const bar = {
    crit: "border-l-cmd-crit", warn: "border-l-cmd-warn",
    accent: "border-l-cmd-accent", muted: "border-l-cmd-border",
  }[tone];
  return (
    <div className={`pl-2 border-l-2 ${bar} py-1.5`}>
      <div className="flex items-center justify-between text-[10px] text-cmd-muted">
        <span className={`font-semibold ${tone === "crit" ? "text-cmd-crit" : tone === "warn" ? "text-cmd-warn" : tone === "accent" ? "text-cmd-accent" : "text-cmd-muted"}`}>
          {title}
        </span>
        <span>{cam} · {time}</span>
      </div>
      <div className="flex items-center gap-2 flex-wrap text-sm mt-0.5">
        {children}
        {conf !== undefined && <ConfidenceBadge value={conf} />}
      </div>
    </div>
  );
}

export function EventFeed({ events, connected }: { events: LiveEvent[]; connected: boolean }) {
  const shown = events.filter((e) =>
    ["speed_event", "traffic_event", "plate_detected", "vehicle_updated", "camera_status"].includes(e.type),
  );
  return (
    <div className="panel flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-cmd-border">
        <span className="panel-title">Real-time AI Events</span>
        <span className="flex items-center gap-1 text-[10px] text-cmd-muted">
          <LiveDot on={connected} /> {connected ? "LIVE" : "RECONNECTING"}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto px-2 divide-y divide-cmd-border/40">
        {shown.length === 0 ? (
          <EmptyState title="Waiting for events" hint="Start the demo or a camera to see live AI activity" />
        ) : (
          shown.map((e, i) => <EventRow key={(e as any)._id ?? i} e={e} />)
        )}
      </div>
    </div>
  );
}
