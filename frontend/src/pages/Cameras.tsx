import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import type { Camera } from "../types";
import { EmptyState, LiveDot, Spinner } from "../components/ui";
import { ConnectCamera } from "../components/ConnectCamera";

export function Cameras() {
  const [cameras, setCameras] = useState<Camera[] | null>(null);
  const [form, setForm] = useState({ name: "", zone: "", location: "", source_type: "file", source_uri: "" });
  const [msg, setMsg] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();

  const [net, setNet] = useState<any | null>(null);
  const load = () => api.cameras().then(setCameras).catch(() => setCameras([]));
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, []);
  useEffect(() => { api.network().then(setNet).catch(() => {}); }, []);

  const add = async () => {
    if (!form.name) { setMsg("Name is required."); return; }
    try {
      await api.createCamera(form);
      setForm({ name: "", zone: "", location: "", source_type: "file", source_uri: "" });
      setMsg("✓ Camera added.");
      load();
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
  };

  const upload = async (file: File) => {
    setUploading(true); setMsg("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("camera_name", file.name);
      const res = await fetch("/api/video/upload", { method: "POST", body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "upload failed");
      setMsg(`✓ Uploaded ${body.camera_id} (${body.size_mb} MB). Start it to analyse.`);
      load();
    } catch (e: any) { setMsg(`Upload error: ${e.message}`); }
    finally { setUploading(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-semibold text-white">Camera Management</h1>
        {net?.urls?.app && (
          <div className="panel px-3 py-1.5 text-xs flex items-center gap-2">
            <span className="text-cmd-muted">Open on other devices:</span>
            <span className="font-mono text-cmd-accent">{net.urls.app}</span>
            {net.frontend_bundled === false && (
              <span className="text-cmd-warn" title="Build the frontend (npm run build) to serve it on the single backend port">
                (dev — allow firewall)
              </span>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        {/* list */}
        <div className="panel">
          <div className="panel-title px-3 py-2 border-b border-cmd-border">Cameras</div>
          {cameras === null ? <Spinner /> : cameras.length === 0 ? (
            <EmptyState title="No cameras" hint="Add one, upload a video, or start the demo." />
          ) : (
            <div className="divide-y divide-cmd-border/40">
              {cameras.map((c) => {
                const online = c.status === "online";
                return (
                  <div key={c.camera_id} className="flex items-center gap-3 px-3 py-2">
                    <LiveDot on={online} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white truncate">
                        <span className="font-mono text-cmd-accent">{c.camera_id}</span> · {c.name}
                      </div>
                      <div className="text-[11px] text-cmd-muted truncate">
                        {c.zone || "—"} · {c.source_type}{c.has_source ? "" : " (no source)"} ·
                        {c.has_calibration ? " calibrated" : " uncalibrated"} · {c.last_environment}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {online ? (
                        <button className="btn text-xs" onClick={() => api.stopCamera(c.camera_id).then(load)}>Stop</button>
                      ) : (
                        <button className="btn btn-primary text-xs"
                          onClick={() => api.startCamera(c.camera_id, true).then(load)}>Start</button>
                      )}
                      <button className="btn text-xs" onClick={() => navigate("/calibration")}>Calib</button>
                      <button className="btn text-xs text-cmd-crit"
                        onClick={() => api.deleteCamera(c.camera_id).then(load)}>Del</button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* connect live / add / upload */}
        <div className="space-y-3">
          <ConnectCamera onConnected={load} />

          <div className="panel p-3 space-y-2">
            <div className="panel-title">Add Camera</div>
            <Input label="Name" v={form.name} on={(v) => setForm({ ...form, name: v })} />
            <Input label="Zone" v={form.zone} on={(v) => setForm({ ...form, zone: v })} />
            <Input label="Location" v={form.location} on={(v) => setForm({ ...form, location: v })} />
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-wider text-cmd-muted">Source Type</span>
              <select className="input" value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value })}>
                <option value="file">Video File</option>
                <option value="rtsp">RTSP Stream</option>
                <option value="webcam">Webcam</option>
              </select>
            </label>
            <Input label={form.source_type === "rtsp" ? "RTSP URL (kept private)" : "Source path / index"}
              v={form.source_uri} on={(v) => setForm({ ...form, source_uri: v })} />
            <button className="btn btn-primary w-full" onClick={add}>Add Camera</button>
          </div>

          <div className="panel p-3 space-y-2">
            <div className="panel-title">Upload Video</div>
            <input ref={fileRef} type="file" accept="video/*" className="hidden"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            <button className="btn w-full" disabled={uploading} onClick={() => fileRef.current?.click()}>
              {uploading ? "Uploading…" : "Choose video file"}
            </button>
            <p className="text-[11px] text-cmd-muted">Creates a camera from an uploaded clip (mp4/avi/mov/mkv/webm).</p>
          </div>

          {msg && <div className="panel p-2 text-xs text-cmd-accent">{msg}</div>}
        </div>
      </div>
    </div>
  );
}

function Input({ label, v, on }: { label: string; v: string; on: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-cmd-muted">{label}</span>
      <input className="input" value={v} onChange={(e) => on(e.target.value)} />
    </label>
  );
}
