import { useEffect, useState } from "react";
import {
  Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../services/api";
import type { Analytics, SpeedEvent } from "../types";
import { EmptyState, Spinner, StatCard } from "../components/ui";

const COLORS = ["#22d3ee", "#38bdf8", "#fbbf24", "#f59e0b", "#ef4444", "#a855f7", "#22c55e"];

export function SpeedAnalytics() {
  const [a, setA] = useState<Analytics | null>(null);
  const [events, setEvents] = useState<SpeedEvent[]>([]);
  const [hours, setHours] = useState(24);

  const load = async () => {
    const [an, se] = await Promise.all([api.analytics(hours), api.speedEvents(100, false)]);
    setA(an);
    setEvents(se);
  };
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [hours]);

  if (!a) return <Spinner label="Loading analytics…" />;

  const dist = Object.entries(a.speed_distribution).map(([name, value]) => ({ name, value }));
  const byHour = Array.from({ length: 24 }, (_, h) => ({ name: `${h}`, value: a.violations_by_hour[h] ?? 0 }));
  const byCam = Object.entries(a.violations_by_camera).map(([name, value]) => ({ name, value }));
  const cats = Object.entries(a.vehicle_categories).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Speed Analytics</h1>
        <select className="input py-1 text-xs" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
          <option value={1}>Last 1h</option>
          <option value={24}>Last 24h</option>
          <option value={168}>Last 7d</option>
        </select>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard label="Avg Speed" value={a.average_speed_kmh} sub="km/h" />
        <StatCard label="Max Est. Speed" value={a.max_speed_kmh} sub="km/h" tone="warn" />
        <StatCard label="Overspeed Events" value={a.overspeed_events} tone="crit" />
        <StatCard label="Speed Samples" value={a.speed_samples} tone="accent" />
        <StatCard label="ANPR Reads" value={a.anpr_reads} tone="accent" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Speed Distribution (km/h)">
          <BarChart data={dist}>
            <XAxis dataKey="name" tick={{ fill: "#6b7a90", fontSize: 11 }} />
            <YAxis tick={{ fill: "#6b7a90", fontSize: 11 }} allowDecimals={false} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey="value" radius={[3, 3, 0, 0]}>
              {dist.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Bar>
          </BarChart>
        </ChartCard>

        <ChartCard title="Violations by Hour">
          <BarChart data={byHour}>
            <XAxis dataKey="name" tick={{ fill: "#6b7a90", fontSize: 10 }} interval={1} />
            <YAxis tick={{ fill: "#6b7a90", fontSize: 11 }} allowDecimals={false} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey="value" fill="#f59e0b" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Violations by Camera">
          {byCam.length === 0 ? <EmptyState title="No violations recorded" /> : (
            <BarChart data={byCam} layout="vertical">
              <XAxis type="number" tick={{ fill: "#6b7a90", fontSize: 11 }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: "#6b7a90", fontSize: 11 }} width={70} />
              <Tooltip contentStyle={TOOLTIP} cursor={{ fill: "#ffffff08" }} />
              <Bar dataKey="value" fill="#ef4444" radius={[0, 3, 3, 0]} />
            </BarChart>
          )}
        </ChartCard>

        <ChartCard title="Vehicle Categories">
          {cats.length === 0 ? <EmptyState title="No categorised vehicles yet" /> : (
            <PieChart>
              <Pie data={cats} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {cats.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={TOOLTIP} />
            </PieChart>
          )}
        </ChartCard>
      </div>

      <div className="panel">
        <div className="panel-title px-3 py-2 border-b border-cmd-border">Recent Speed Events</div>
        {events.length === 0 ? <EmptyState title="No speed events" hint="Run the demo to generate data." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase text-cmd-muted border-b border-cmd-border">
                  <th className="text-left px-3 py-2">Plate</th>
                  <th className="text-left px-3 py-2">Camera</th>
                  <th className="text-right px-3 py-2">Speed</th>
                  <th className="text-right px-3 py-2">Limit</th>
                  <th className="text-left px-3 py-2">Method</th>
                  <th className="text-left px-3 py-2">Status</th>
                  <th className="text-left px-3 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="border-b border-cmd-border/40">
                    <td className="px-3 py-2 font-mono text-white">{e.plate_number || e.tracking_id || "—"}</td>
                    <td className="px-3 py-2 font-mono text-cmd-accent">{e.camera_id}</td>
                    <td className={`px-3 py-2 text-right font-mono ${e.is_violation ? "text-cmd-crit" : ""}`}>{e.speed_kmh.toFixed(1)}</td>
                    <td className="px-3 py-2 text-right text-cmd-muted">{e.speed_limit_kmh}</td>
                    <td className="px-3 py-2 text-xs text-cmd-muted">{e.method}</td>
                    <td className="px-3 py-2">{e.is_violation
                      ? <span className="chip bg-cmd-crit/15 text-cmd-crit">VIOLATION</span>
                      : <span className="chip bg-cmd-ok/15 text-cmd-ok">OK</span>}</td>
                    <td className="px-3 py-2 text-xs text-cmd-muted">{new Date(e.timestamp).toLocaleTimeString()}</td>
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

const TOOLTIP = { background: "#111722", border: "1px solid #1f2a3a", borderRadius: 8, color: "#c7d3e2", fontSize: 12 };

function ChartCard({ title, children }: { title: string; children: React.ReactElement }) {
  return (
    <div className="panel p-3">
      <div className="panel-title mb-2">{title}</div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
      </div>
    </div>
  );
}
