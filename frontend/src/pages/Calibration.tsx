import { useEffect, useRef, useState } from "react";
import { api, calibFrameUrl } from "../services/api";
import type { Camera } from "../types";
import { EmptyState, Spinner } from "../components/ui";

type Pt = [number, number];

export function Calibration() {
  const [cameras, setCameras] = useState<Camera[] | null>(null);
  const [cam, setCam] = useState<string>("");
  const [points, setPoints] = useState<Pt[]>([]);
  const [distance, setDistance] = useState("24");
  const [limit, setLimit] = useState("60");
  const [direction, setDirection] = useState("right");
  const [result, setResult] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [dims, setDims] = useState<{ w: number; h: number }>({ w: 1280, h: 720 });

  useEffect(() => {
    api.cameras().then((cs) => {
      setCameras(cs);
      if (cs[0]) setCam(cs[0].camera_id);
    }).catch(() => setCameras([]));
  }, []);

  useEffect(() => {
    if (!cam) return;
    setPoints([]); setResult(null); setMsg("");
    api.calibration(cam).then((c) => {
      if (c && c.line_a?.length === 2 && c.line_b?.length === 2) {
        setPoints([c.line_a[0], c.line_a[1], c.line_b[0], c.line_b[1]]);
        setDistance(String(c.real_distance_m || 24));
        setLimit(String(c.speed_limit_kmh || 60));
        setDirection(c.direction || "right");
      }
    }).catch(() => {});
  }, [cam]);

  const onImgClick = (e: React.MouseEvent<HTMLImageElement>) => {
    if (points.length >= 4) return;
    const img = imgRef.current!;
    const rect = img.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * dims.w;
    const y = ((e.clientY - rect.top) / rect.height) * dims.h;
    setPoints((p) => [...p, [Math.round(x), Math.round(y)]]);
  };

  const save = async () => {
    if (points.length < 4) { setMsg("Place all 4 points (2 per line) first."); return; }
    try {
      await api.saveCalibration(cam, {
        method: "dual_line",
        line_a: [points[0], points[1]],
        line_b: [points[2], points[3]],
        real_distance_m: Number(distance),
        speed_limit_kmh: Number(limit),
        direction,
        frame_width: dims.w,
        frame_height: dims.h,
      });
      setMsg("✓ Calibration saved.");
      test();
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
  };

  const test = async () => {
    try {
      const r = await api.testCalibration(cam);
      setResult(r);
    } catch (e: any) { setMsg(`Test error: ${e.message}`); }
  };

  if (cameras === null) return <Spinner label="Loading cameras…" />;
  if (cameras.length === 0)
    return <EmptyState title="No cameras" hint="Start the demo or add a camera first." />;

  const lineA = points.slice(0, 2);
  const lineB = points.slice(2, 4);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-semibold text-white">Speed Calibration</h1>
        <select className="input" value={cam} onChange={(e) => setCam(e.target.value)}>
          {cameras.map((c) => <option key={c.camera_id} value={c.camera_id}>{c.camera_id} · {c.name}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
        <div className="panel p-3">
          <div className="panel-title mb-2">
            Frame · click to place {points.length < 2 ? "LINE A" : points.length < 4 ? "LINE B" : "(all set)"} ({points.length}/4)
          </div>
          <div className="relative select-none">
            <img
              ref={imgRef}
              src={calibFrameUrl(cam, 40)}
              alt="calibration frame"
              onClick={onImgClick}
              onLoad={(e) => setDims({ w: e.currentTarget.naturalWidth || 1280, h: e.currentTarget.naturalHeight || 720 })}
              className="w-full rounded border border-cmd-border cursor-crosshair bg-black"
            />
            <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox={`0 0 ${dims.w} ${dims.h}`} preserveAspectRatio="none">
              {lineA.length === 2 && <line x1={lineA[0][0]} y1={lineA[0][1]} x2={lineA[1][0]} y2={lineA[1][1]} stroke="#22d3ee" strokeWidth={3} />}
              {lineB.length === 2 && <line x1={lineB[0][0]} y1={lineB[0][1]} x2={lineB[1][0]} y2={lineB[1][1]} stroke="#fbbf24" strokeWidth={3} />}
              {points.map((p, i) => (
                <circle key={i} cx={p[0]} cy={p[1]} r={6} fill={i < 2 ? "#22d3ee" : "#fbbf24"} stroke="#0a0e14" strokeWidth={2} />
              ))}
            </svg>
          </div>
          <div className="flex gap-2 mt-2">
            <button className="btn text-xs" onClick={() => { setPoints([]); setResult(null); }}>Reset Points</button>
            <span className="text-[11px] text-cmd-muted self-center">
              Line A (cyan) &amp; Line B (amber) mark where the known real-world distance is measured.
            </span>
          </div>
        </div>

        <div className="space-y-3">
          <div className="panel p-3 space-y-2">
            <div className="panel-title">Parameters</div>
            <LabeledInput label="Real distance between lines (m)" value={distance} onChange={setDistance} />
            <LabeledInput label="Speed limit (km/h)" value={limit} onChange={setLimit} />
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-wider text-cmd-muted">Allowed direction</span>
              <select className="input" value={direction} onChange={(e) => setDirection(e.target.value)}>
                {["right", "left", "up", "down"].map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
            <div className="flex gap-2 pt-1">
              <button className="btn btn-primary flex-1" onClick={save}>Save</button>
              <button className="btn flex-1" onClick={test}>Test</button>
            </div>
            {msg && <div className="text-xs text-cmd-accent">{msg}</div>}
          </div>

          <div className="panel p-3">
            <div className="panel-title mb-2">Calibration Test</div>
            {!result ? (
              <p className="text-xs text-cmd-muted">
                Save or test to validate the geometry against a synthetic crossing.
              </p>
            ) : result.ok ? (
              <div className="space-y-1 text-sm">
                <Row k="Estimated speed" v={`${result.measurement.speed_kmh} km/h`} />
                <Row k="Distance" v={`${result.measurement.distance_m} m`} />
                <Row k="Elapsed" v={`${result.measurement.elapsed_s} s`} />
                <Row k="Method" v={result.measurement.method} />
                <Row k="Confidence" v={`${Math.round(result.measurement.confidence * 100)}%`} />
              </div>
            ) : (
              <div className="text-xs text-cmd-warn">{result.message}</div>
            )}
          </div>

          <div className="panel p-3 text-[11px] text-cmd-muted leading-snug">
            <b className="text-cmd-text">Methodology.</b> Speed is derived from calibrated scene geometry
            (dual virtual lines a known distance apart), not raw pixels. Accuracy depends on camera
            perspective and frame rate; results are labelled <i>Estimated</i> and require human verification.
          </div>
        </div>
      </div>
    </div>
  );
}

function LabeledInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-cmd-muted">{label}</span>
      <input className="input" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between border-b border-cmd-border/30 py-1 last:border-0">
      <span className="text-cmd-muted">{k}</span>
      <span className="font-mono text-white">{v}</span>
    </div>
  );
}
