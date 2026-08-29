import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, assetUrl } from "../services/api";
import type { SpeedEvent, VehicleDetail as VD } from "../types";
import { ConfidenceBadge, EmptyState, Spinner, VerifyTag } from "../components/ui";

export function VehicleDetail() {
  const { uid } = useParams();
  const [data, setData] = useState<VD | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<SpeedEvent | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!uid) return;
    api.vehicleDetail(uid).then((d) => {
      setData(d);
      setSelected(d.speed_events[0] ?? null);
    }).catch((e) => setError(e.message));
  }, [uid]);

  if (error) return <EmptyState title="Vehicle not found" hint={error} />;
  if (!data) return <Spinner label="Loading vehicle intelligence…" />;

  const v = data.vehicle;
  const journey = data.journey;

  return (
    <div className="space-y-4">
      <button className="btn text-xs" onClick={() => navigate(-1)}>← Back</button>

      {/* header */}
      <div className="panel p-4 flex flex-wrap items-center gap-4">
        <div>
          <div className="text-[10px] uppercase text-cmd-muted">Vehicle ID</div>
          <div className="text-lg font-mono text-cmd-accent">{v.vehicle_uid}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase text-cmd-muted">Plate</div>
          <div className="text-lg font-mono text-white tracking-wider flex items-center gap-2">
            {v.plate_number || "UNKNOWN"}
            {v.plate_number && v.plate_confidence < 0.75 && <VerifyTag />}
          </div>
        </div>
        <Info label="Type" value={v.vehicle_class} />
        <Info label="Color" value={v.color} />
        <Info label="First Seen" value={new Date(v.first_seen).toLocaleString()} />
        <Info label="Last Seen" value={new Date(v.last_seen).toLocaleString()} />
        <Info label="Observations" value={String(v.observation_count)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Journey */}
        <div className="panel p-4">
          <div className="panel-title mb-3">Cross-Camera Journey</div>
          {!journey || journey.path.length === 0 ? (
            <EmptyState title="No multi-camera journey yet"
              hint="Journeys build as the vehicle is re-identified across cameras." />
          ) : (
            <>
              <div className="flex items-center gap-2 text-xs text-cmd-muted mb-3">
                <span>{journey.hop_count} hop(s)</span>·
                <span>association</span><ConfidenceBadge value={journey.association_confidence} />
              </div>
              <ol className="relative border-l-2 border-cmd-border ml-2 space-y-4">
                {journey.path.map((hop, i) => (
                  <li key={i} className="ml-4">
                    <span className="absolute -left-[7px] w-3 h-3 rounded-full bg-cmd-accent border-2 border-cmd-bg" />
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-cmd-accent">{hop.camera_id}</span>
                      <span className="text-[11px] text-cmd-muted">{new Date(hop.timestamp).toLocaleTimeString()}</span>
                    </div>
                    {hop.speed_kmh != null && (
                      <div className="text-xs text-cmd-text">{Math.round(hop.speed_kmh)} km/h</div>
                    )}
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>

        {/* Speed events + explainability */}
        <div className="panel p-4">
          <div className="panel-title mb-3">Speed Events</div>
          {data.speed_events.length === 0 ? (
            <EmptyState title="No speed measurements" hint="Requires calibrated cameras." />
          ) : (
            <div className="flex flex-wrap gap-2 mb-3">
              {data.speed_events.map((se) => (
                <button key={se.id} onClick={() => setSelected(se)}
                  className={`btn text-xs ${selected?.id === se.id ? "btn-primary" : ""} ${se.is_violation ? "text-cmd-crit" : ""}`}>
                  {se.camera_id} · {Math.round(se.speed_kmh)}km/h
                </button>
              ))}
            </div>
          )}
          {selected && <ExplainSpeed se={selected} />}
        </div>
      </div>

      {/* Plate reads */}
      <div className="panel p-4">
        <div className="panel-title mb-3">ANPR Reads</div>
        {data.plate_reads.length === 0 ? (
          <EmptyState title="No plate reads" />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {data.plate_reads.map((pr) => (
              <div key={pr.id} className="panel p-2 bg-cmd-panel2">
                {pr.crop_path && (
                  <img src={assetUrl(pr.crop_path)} alt="plate" className="w-full h-12 object-contain bg-black rounded mb-1"
                    onError={(e) => (e.currentTarget.style.display = "none")} />
                )}
                <div className="font-mono text-white tracking-wider text-sm">{pr.normalized_text || "—"}</div>
                <div className="text-[10px] text-cmd-muted">raw: {pr.raw_text}</div>
                <div className="flex items-center justify-between mt-1">
                  <ConfidenceBadge value={pr.confidence} />
                  {pr.needs_verification ? <VerifyTag /> : <span className="text-[10px] text-cmd-ok">OK</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ExplainSpeed({ se }: { se: SpeedEvent }) {
  const rows: [string, string][] = [
    ["Vehicle", se.plate_number || se.tracking_id || "—"],
    ["Measurement method", se.method],
    ["Reference distance", `${se.distance_m.toFixed(1)} m`],
    ["Elapsed time", `${se.elapsed_s.toFixed(3)} s`],
    ["Estimated speed", `${se.speed_kmh.toFixed(2)} km/h`],
    ["Configured limit", `${se.speed_limit_kmh.toFixed(0)} km/h`],
    ["Excess", `${se.excess_kmh.toFixed(2)} km/h`],
  ];
  return (
    <div className="bg-cmd-bg rounded-md border border-cmd-border p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-cmd-accent">EXPLAINABLE SPEED RESULT</span>
        {se.is_violation
          ? <span className="chip bg-cmd-crit/15 text-cmd-crit border border-cmd-crit/30">VIOLATION</span>
          : <span className="chip bg-cmd-ok/15 text-cmd-ok">WITHIN LIMIT</span>}
      </div>
      <table className="w-full text-sm">
        <tbody>
          {rows.map(([k, val]) => (
            <tr key={k} className="border-b border-cmd-border/30 last:border-0">
              <td className="py-1 text-cmd-muted">{k}</td>
              <td className="py-1 text-right font-mono text-white">{val}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between mt-2 text-xs">
        <span className="text-cmd-muted">Confidence</span>
        <ConfidenceBadge value={se.confidence} />
      </div>
      <p className="text-[10px] text-cmd-muted mt-2 leading-snug">
        Estimated using scene calibration. CCTV perspective and frame rate affect precision — treat as an
        estimate requiring human verification for enforcement.
      </p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase text-cmd-muted">{label}</div>
      <div className="text-sm text-white capitalize">{value}</div>
    </div>
  );
}
