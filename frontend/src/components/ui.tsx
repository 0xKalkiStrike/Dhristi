import type { ReactNode } from "react";

export function LiveDot({ on }: { on: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${on ? "bg-cmd-ok live-dot" : "bg-cmd-muted"}`}
      title={on ? "live" : "offline"}
    />
  );
}

export function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round((value ?? 0) * 100);
  const low = pct < 75;
  return (
    <span
      className={`chip ${low ? "bg-cmd-warn/15 text-cmd-warn" : "bg-cmd-ok/15 text-cmd-ok"}`}
      title={low ? "Low confidence — human verification recommended" : "Confidence"}
    >
      {pct}%
    </span>
  );
}

const SEV: Record<string, string> = {
  critical: "bg-cmd-crit/15 text-cmd-crit border border-cmd-crit/30",
  warning: "bg-cmd-warn/15 text-cmd-warn border border-cmd-warn/30",
  info: "bg-cmd-accent/10 text-cmd-accent border border-cmd-accent/30",
};
export function SeverityChip({ severity }: { severity: string }) {
  return <span className={`chip uppercase ${SEV[severity] || SEV.info}`}>{severity}</span>;
}

const EVENT_LABEL: Record<string, string> = {
  overspeed: "OVERSPEED",
  wrong_way: "WRONG WAY",
  stopped_vehicle: "STOPPED",
  abnormal_dwell: "DWELL",
  restricted_zone: "RESTRICTED",
  congestion: "CONGESTION",
};
export function eventLabel(t: string) {
  return EVENT_LABEL[t] || t.toUpperCase();
}

export function StatCard({
  label, value, sub, tone = "default",
}: { label: string; value: ReactNode; sub?: string; tone?: "default" | "warn" | "crit" | "ok" | "accent" }) {
  const toneCls = {
    default: "text-white",
    warn: "text-cmd-warn",
    crit: "text-cmd-crit",
    ok: "text-cmd-ok",
    accent: "text-cmd-accent",
  }[tone];
  return (
    <div className="panel p-3 flex flex-col gap-1">
      <div className="panel-title">{label}</div>
      <div className={`text-2xl font-semibold font-mono ${toneCls}`}>{value}</div>
      {sub && <div className="text-[11px] text-cmd-muted">{sub}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-cmd-muted text-sm py-6 justify-center">
      <span className="w-4 h-4 border-2 border-cmd-border border-t-cmd-accent rounded-full animate-spin" />
      {label || "Loading…"}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="text-center py-8 text-cmd-muted">
      <div className="text-sm font-medium">{title}</div>
      {hint && <div className="text-[11px] mt-1 opacity-70">{hint}</div>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="panel p-3 border-cmd-crit/40 bg-cmd-crit/5 text-cmd-crit text-sm">
      ⚠ {message}
    </div>
  );
}

export function VerifyTag() {
  return (
    <span className="chip bg-cmd-warn/15 text-cmd-warn border border-cmd-warn/30">
      NEEDS VERIFICATION
    </span>
  );
}
