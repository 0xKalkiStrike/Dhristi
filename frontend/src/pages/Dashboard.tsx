import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { CameraTile } from "../components/CameraTile";
import { EventFeed } from "../components/EventFeed";
import { useLiveEvents } from "../hooks/useLiveEvents";
import type { Analytics, Camera, PipelineStatus } from "../types";
import { EmptyState, Spinner, StatCard } from "../components/ui";

const GRID = { 1: "grid-cols-1", 4: "grid-cols-2", 9: "grid-cols-3", 16: "grid-cols-4" } as const;

export function Dashboard() {
  const { events, connected } = useLiveEvents(80);
  const [cameras, setCameras] = useState<Camera[] | null>(null);
  const [pipelines, setPipelines] = useState<Record<string, PipelineStatus>>({});
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [grid, setGrid] = useState<keyof typeof GRID>(4);
  const [zone, setZone] = useState<string>("all");
  const navigate = useNavigate();

  const refresh = async () => {
    try {
      const [cams, pl, an] = await Promise.all([api.cameras(), api.pipelines(), api.analytics(24)]);
      setCameras(cams);
      const map: Record<string, PipelineStatus> = {};
      pl.pipelines.forEach((p) => p && (map[p.camera_id] = p));
      setPipelines(map);
      setAnalytics(an);
    } catch {
      setCameras([]);
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);

  const zones = useMemo(
    () => ["all", ...Array.from(new Set((cameras ?? []).map((c) => c.zone).filter(Boolean)))],
    [cameras],
  );
  const visible = useMemo(() => {
    const list = (cameras ?? []).filter((c) => zone === "all" || c.zone === zone);
    return list.slice(0, grid);
  }, [cameras, zone, grid]);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-4 h-full">
      <div className="flex flex-col gap-4 min-w-0">
        {/* controls */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className="panel-title">Unified Camera Grid</span>
            <select className="input py-1 text-xs" value={zone} onChange={(e) => setZone(e.target.value)}>
              {zones.map((z) => <option key={z} value={z}>{z === "all" ? "All Zones" : z}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-1">
            {([1, 4, 9, 16] as const).map((g) => (
              <button key={g} onClick={() => setGrid(g)}
                className={`btn py-1 px-2 text-xs ${grid === g ? "btn-primary" : ""}`}>{g}</button>
            ))}
          </div>
        </div>

        {/* grid */}
        {cameras === null ? (
          <Spinner label="Loading cameras…" />
        ) : cameras.length === 0 ? (
          <div className="panel p-8 text-center space-y-4">
            <div className="text-3xl opacity-40">🎥</div>
            <div className="text-base font-semibold text-white">No Live Cameras Connected</div>
            <p className="text-xs text-cmd-muted max-w-md mx-auto">
              To view real AI detections, connect your laptop/phone camera or upload a video clip.
            </p>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                className="btn btn-primary text-xs font-semibold px-4 py-2"
                onClick={() => navigate("/cameras")}
              >
                ▶ Connect Live Camera (Real Data)
              </button>
            </div>
          </div>
        ) : (
          <div className={`grid ${GRID[grid]} gap-3`}>
            {visible.map((c) => (
              <CameraTile key={c.camera_id} camera={c} status={pipelines[c.camera_id]}
                onClick={() => navigate("/search", { state: { camera: c.camera_id } })} />
            ))}
          </div>
        )}

        {/* analytics */}
        <div>
          <div className="panel-title mb-2">Operational Analytics · last 24h</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatCard label="Vehicles" value={analytics?.vehicles_detected ?? 0} tone="accent" />
            <StatCard label="Avg Speed" value={`${analytics?.average_speed_kmh ?? 0}`} sub="km/h" />
            <StatCard label="Max Speed" value={`${analytics?.max_speed_kmh ?? 0}`} sub="km/h est." tone="warn" />
            <StatCard label="Overspeed" value={analytics?.overspeed_events ?? 0} tone="crit" />
            <StatCard label="ANPR Reads" value={analytics?.anpr_reads ?? 0} tone="accent" />
            <StatCard label="Uptime" value={`${analytics?.camera_uptime_pct ?? 0}%`} tone="ok" />
          </div>
        </div>
      </div>

      {/* right rail */}
      <div className="h-[calc(100vh-8rem)] xl:h-auto min-h-[400px]">
        <EventFeed events={events} connected={connected} />
      </div>
    </div>
  );
}
