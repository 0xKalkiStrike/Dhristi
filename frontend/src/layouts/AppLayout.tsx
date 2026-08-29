import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import type { Analytics, Health } from "../types";
import { LiveDot } from "../components/ui";

const NAV = [
  { to: "/", label: "Unified View", icon: "▦" },
  { to: "/search", label: "Selective Analysis", icon: "⌕" },
  { to: "/speed", label: "Speed Analytics", icon: "⚡" },
  { to: "/calibration", label: "Speed Calibration", icon: "◈" },
  { to: "/cameras", label: "Camera Management", icon: "▤" },
];

export function AppLayout() {
  const [health, setHealth] = useState<Health | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const refresh = async () => {
    try {
      const [h, a] = await Promise.all([api.health(), api.analytics(24)]);
      setHealth(h);
      setAnalytics(a);
    } catch {
      setHealth(null);
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  const startDemo = async () => {
    setBusy(true);
    try {
      await api.startDemo();
      navigate("/");
    } finally {
      setTimeout(() => setBusy(false), 1500);
    }
  };
  const stopDemo = async () => {
    setBusy(true);
    try { await api.stopDemo(); } finally { setBusy(false); }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Top bar */}
      <header className="h-14 shrink-0 border-b border-cmd-border bg-cmd-panel flex items-center px-4 gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded bg-cmd-accent/15 border border-cmd-accent/40 flex items-center justify-center text-cmd-accent font-bold">
            ◉
          </div>
          <div className="leading-tight">
            <div className="text-white font-bold tracking-wide">DRISHTI-V</div>
            <div className="text-[9px] text-cmd-muted uppercase tracking-wider hidden sm:block">
              Dynamic Road Intelligence &amp; Surveillance
            </div>
          </div>
        </div>

        <div className="flex-1 flex items-center gap-4 justify-center overflow-x-auto">
          <TopStat label="System" value={health ? "ONLINE" : "OFFLINE"} tone={health ? "ok" : "crit"} dot={!!health} />
          <TopStat label="AI Runtime" value={health?.ai_runtime ?? "—"} tone="accent" />
          <TopStat label="Cameras" value={`${analytics?.cameras_online ?? 0}/${analytics?.cameras_total ?? 0}`} />
          <TopStat label="Vehicles 24h" value={analytics?.vehicles_detected ?? 0} />
          <TopStat label="Violations" value={analytics?.overspeed_events ?? 0} tone="warn" />
          <TopStat label="ANPR" value={analytics?.anpr_reads ?? 0} tone="accent" />
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button className="btn btn-primary" onClick={startDemo} disabled={busy}>
            {busy ? "…" : "▶ START DEMO"}
          </button>
          <button className="btn" onClick={stopDemo} disabled={busy}>■ Stop</button>
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Sidebar */}
        <nav className="w-52 shrink-0 border-r border-cmd-border bg-cmd-panel p-3 hidden md:flex flex-col gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-cmd-accent/15 text-cmd-accent border border-cmd-accent/30"
                    : "text-cmd-text hover:bg-cmd-panel2 border border-transparent"
                }`
              }
            >
              <span className="opacity-70">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
          <div className="mt-auto pt-3 border-t border-cmd-border text-[10px] text-cmd-muted space-y-1">
            <div className="flex items-center gap-1"><LiveDot on={!!health} /> {health?.database === "ok" ? "SQL connected" : "DB error"}</div>
            <div className="flex items-center gap-1">
              <LiveDot on={!!health?.mongo_connected} />
              {health?.mongo_connected ? "Mongo connected" : health?.mongo_enabled ? "Mongo off" : "Mongo disabled"}
            </div>
            <div>Detector: {health?.detector_backend ?? "—"}</div>
            <div>OCR: {health?.ocr_engine ?? "—"}</div>
            <div>Device: {health?.device ?? "—"}</div>
            <div className="opacity-60">v{health?.version ?? "1.0.0"}</div>
          </div>
        </nav>

        <main className="flex-1 min-w-0 overflow-y-auto p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function TopStat({ label, value, tone = "default", dot }: {
  label: string; value: React.ReactNode; tone?: "default" | "ok" | "warn" | "crit" | "accent"; dot?: boolean;
}) {
  const c = { default: "text-white", ok: "text-cmd-ok", warn: "text-cmd-warn", crit: "text-cmd-crit", accent: "text-cmd-accent" }[tone];
  return (
    <div className="text-center shrink-0">
      <div className="text-[9px] uppercase tracking-wider text-cmd-muted">{label}</div>
      <div className={`text-sm font-mono font-semibold flex items-center gap-1 justify-center ${c}`}>
        {dot !== undefined && <LiveDot on={dot} />} {value}
      </div>
    </div>
  );
}
