import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import type { Camera } from "../types";
import { ConfidenceBadge, EmptyState, Spinner } from "../components/ui";

interface Filters {
  plate: string; vehicle_type: string; color: string; camera_id: string;
  min_speed: string; max_speed: string; event_type: string; min_confidence: string; direction: string;
}
const EMPTY: Filters = {
  plate: "", vehicle_type: "", color: "", camera_id: "",
  min_speed: "", max_speed: "", event_type: "", min_confidence: "", direction: "",
};

export function Search() {
  const location = useLocation() as { state?: { camera?: string } };
  const [filters, setFilters] = useState<Filters>({ ...EMPTY, camera_id: location.state?.camera ?? "" });
  const [results, setResults] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const navigate = useNavigate();

  useEffect(() => { api.cameras().then(setCameras).catch(() => setCameras([])); }, []);
  useEffect(() => { runSearch(); /* initial */ }, []); // eslint-disable-line

  const set = (k: keyof Filters, v: string) => setFilters((f) => ({ ...f, [k]: v }));

  const runSearch = async () => {
    setLoading(true);
    try {
      const res = await api.search({
        plate: filters.plate || undefined,
        vehicle_type: filters.vehicle_type || undefined,
        color: filters.color || undefined,
        camera_id: filters.camera_id || undefined,
        min_speed: filters.min_speed || undefined,
        max_speed: filters.max_speed || undefined,
        event_type: filters.event_type || undefined,
        min_confidence: filters.min_confidence || undefined,
        direction: filters.direction || undefined,
        limit: 200,
      });
      setResults(res.results);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Selective Analysis</h1>
        <span className="text-xs text-cmd-muted">Search vehicles across all cameras</span>
      </div>

      {/* search + filters */}
      <div className="panel p-4 space-y-3">
        <div className="flex gap-2">
          <input
            className="input flex-1 font-mono tracking-wider"
            placeholder="Plate number e.g. GJ01AB1234"
            value={filters.plate}
            onChange={(e) => set("plate", e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
          />
          <button className="btn btn-primary" onClick={runSearch}>⌕ Search</button>
          <button className="btn" onClick={() => { setFilters(EMPTY); }}>Reset</button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          <Select label="Vehicle Type" value={filters.vehicle_type} onChange={(v) => set("vehicle_type", v)}
            options={["", "car", "motorcycle", "bus", "truck", "bicycle"]} />
          <Select label="Color" value={filters.color} onChange={(v) => set("color", v)}
            options={["", "white", "black", "silver", "gray", "red", "blue", "green", "yellow", "orange"]} />
          <Select label="Camera" value={filters.camera_id} onChange={(v) => set("camera_id", v)}
            options={["", ...cameras.map((c) => c.camera_id)]} />
          <Select label="Event Type" value={filters.event_type} onChange={(v) => set("event_type", v)}
            options={["", "overspeed", "wrong_way", "stopped_vehicle", "abnormal_dwell", "restricted_zone", "congestion"]} />
          <Field label="Min Speed" value={filters.min_speed} onChange={(v) => set("min_speed", v)} placeholder="km/h" />
          <Field label="Max Speed" value={filters.max_speed} onChange={(v) => set("max_speed", v)} placeholder="km/h" />
          <Field label="Min Confidence" value={filters.min_confidence} onChange={(v) => set("min_confidence", v)} placeholder="0-1" />
          <Select label="Direction" value={filters.direction} onChange={(v) => set("direction", v)}
            options={["", "left", "right", "up", "down"]} />
        </div>
      </div>

      {/* results */}
      <div className="panel">
        <div className="flex items-center justify-between px-3 py-2 border-b border-cmd-border">
          <span className="panel-title">Results</span>
          <span className="text-xs text-cmd-muted">{results?.length ?? 0} observations</span>
        </div>
        {loading ? (
          <Spinner label="Searching…" />
        ) : !results || results.length === 0 ? (
          <EmptyState title="No matching observations" hint="Adjust filters or run the demo to populate data." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase text-cmd-muted border-b border-cmd-border">
                  <th className="text-left px-3 py-2">Plate</th>
                  <th className="text-left px-3 py-2">Type</th>
                  <th className="text-left px-3 py-2">Color</th>
                  <th className="text-left px-3 py-2">Camera</th>
                  <th className="text-right px-3 py-2">Speed</th>
                  <th className="text-left px-3 py-2">Time</th>
                  <th className="text-right px-3 py-2">Conf</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i}
                    onClick={() => r.vehicle_uid && navigate(`/vehicle/${r.vehicle_uid}`)}
                    className="border-b border-cmd-border/40 hover:bg-cmd-panel2 cursor-pointer">
                    <td className="px-3 py-2 font-mono text-white tracking-wider">{r.plate_number || "—"}</td>
                    <td className="px-3 py-2 capitalize">{r.vehicle_class}</td>
                    <td className="px-3 py-2 capitalize text-cmd-muted">{r.color}</td>
                    <td className="px-3 py-2 font-mono text-cmd-accent">{r.camera_id}</td>
                    <td className="px-3 py-2 text-right font-mono">{r.speed_kmh ? `${Math.round(r.speed_kmh)} km/h` : "—"}</td>
                    <td className="px-3 py-2 text-cmd-muted text-xs">{new Date(r.timestamp).toLocaleString()}</td>
                    <td className="px-3 py-2 text-right"><ConfidenceBadge value={r.detection_confidence} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-cmd-muted">{label}</span>
      <input className="input" value={value} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: string[];
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-cmd-muted">{label}</span>
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o} value={o}>{o === "" ? "Any" : o}</option>)}
      </select>
    </label>
  );
}
