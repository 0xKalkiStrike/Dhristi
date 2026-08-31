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
  const [busyMap, setBusyMap] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();

  const [net, setNet] = useState<any | null>(null);

  const load = () =>
    api
      .cameras()
      .then(setCameras)
      .catch(() => setCameras([]));

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    api
      .network()
      .then(setNet)
      .catch(() => {});
  }, []);

  const handleStart = async (cameraId: string) => {
    setBusyMap((m) => ({ ...m, [cameraId]: "starting" }));
    setMsg("");
    try {
      await api.startCamera(cameraId, true);
      setMsg(`✓ Started camera ${cameraId}`);
      await load();
    } catch (err: any) {
      setMsg(`❌ Failed to start ${cameraId}: ${err.message}`);
    } finally {
      setBusyMap((m) => {
        const copy = { ...m };
        delete copy[cameraId];
        return copy;
      });
    }
  };

  const handleStop = async (cameraId: string) => {
    setBusyMap((m) => ({ ...m, [cameraId]: "stopping" }));
    setMsg("");
    try {
      await api.stopCamera(cameraId);
      setMsg(`✓ Stopped camera ${cameraId}`);
      await load();
    } catch (err: any) {
      setMsg(`❌ Error stopping ${cameraId}: ${err.message}`);
    } finally {
      setBusyMap((m) => {
        const copy = { ...m };
        delete copy[cameraId];
        return copy;
      });
    }
  };

  const handleDelete = async (cameraId: string) => {
    setBusyMap((m) => ({ ...m, [cameraId]: "deleting" }));
    setMsg("");
    try {
      await api.deleteCamera(cameraId);
      setMsg(`✓ Deleted camera ${cameraId}`);
      await load();
    } catch (err: any) {
      setMsg(`❌ Error deleting ${cameraId}: ${err.message}`);
    } finally {
      setBusyMap((m) => {
        const copy = { ...m };
        delete copy[cameraId];
        return copy;
      });
    }
  };

  const deleteErrorCameras = async () => {
    if (!cameras) return;
    const errorCams = cameras.filter((c) => c.status === "error" || (c.status === "offline" && c.source_type === "rtsp" && !c.has_source));
    for (const c of errorCams) {
      try {
        await api.deleteCamera(c.camera_id);
      } catch {}
    }
    setMsg(`✓ Cleaned ${errorCams.length} inactive/error cameras`);
    load();
  };

  const add = async () => {
    if (!form.name.trim()) {
      setMsg("❌ Name is required.");
      return;
    }
    try {
      await api.createCamera(form);
      setForm({ name: "", zone: "", location: "", source_type: "file", source_uri: "" });
      setMsg("✓ Camera added successfully.");
      load();
    } catch (e: any) {
      setMsg(`❌ Error: ${e.message}`);
    }
  };

  const upload = async (file: File) => {
    setUploading(true);
    setMsg("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("camera_name", file.name);
      const res = await fetch("/api/video/upload", { method: "POST", body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "upload failed");
      setMsg(`✓ Uploaded ${body.camera_id} (${body.size_mb} MB). Click Start to analyse.`);
      load();
    } catch (e: any) {
      setMsg(`❌ Upload error: ${e.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-semibold text-white">Camera Management</h1>
        {net?.urls?.app && (
          <div className="panel px-3 py-1.5 text-xs flex items-center gap-2">
            <span className="text-cmd-muted">Open on other devices:</span>
            <span className="font-mono text-cmd-accent">{net.urls.app}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-4">
        {/* List */}
        <div className="panel">
          <div className="panel-title px-3 py-2 border-b border-cmd-border flex items-center justify-between">
            <span>Configured Cameras ({cameras?.length ?? 0})</span>
            {cameras && cameras.some((c) => c.status === "error") && (
              <button
                onClick={deleteErrorCameras}
                className="btn text-[11px] text-cmd-crit hover:bg-cmd-crit/10 px-2 py-0.5 border border-cmd-crit/30"
              >
                Clear Error Cameras
              </button>
            )}
          </div>

          {cameras === null ? (
            <Spinner label="Loading cameras…" />
          ) : cameras.length === 0 ? (
            <EmptyState title="No cameras" hint="Connect a webcam, upload a video, or start the demo." />
          ) : (
            <div className="divide-y divide-cmd-border/40">
              {cameras.map((c) => {
                const online = c.status === "online";
                const isError = c.status === "error";
                const busy = busyMap[c.camera_id];

                return (
                  <div key={c.camera_id} className="flex items-center gap-3 px-3 py-2.5 hover:bg-cmd-panel2/50 transition-colors">
                    <LiveDot on={online} />

                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-white truncate flex items-center gap-2">
                        <span className="font-mono text-cmd-accent">{c.camera_id}</span>
                        <span>· {c.name}</span>
                        {online && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] bg-cmd-ok/20 text-cmd-ok font-mono font-bold">
                            ONLINE {c.fps > 0 ? `(${c.fps.toFixed(1)} fps)` : ""}
                          </span>
                        )}
                        {isError && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] bg-cmd-crit/20 text-cmd-crit font-mono font-bold">
                            ERROR
                          </span>
                        )}
                        {!online && !isError && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] bg-white/10 text-cmd-muted font-mono">
                            OFFLINE
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-cmd-muted truncate mt-0.5">
                        {c.zone || "—"} · <span className="uppercase">{c.source_type}</span>
                        {c.has_source ? "" : " (no source)"} · {c.has_calibration ? "calibrated" : "uncalibrated"}
                        {c.last_environment !== "unknown" ? ` · ${c.last_environment}` : ""}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {online ? (
                        <button
                          className="btn text-xs px-2.5 py-1"
                          disabled={!!busy}
                          onClick={() => handleStop(c.camera_id)}
                        >
                          {busy === "stopping" ? "Stopping…" : "Stop"}
                        </button>
                      ) : (
                        <button
                          className="btn btn-primary text-xs px-2.5 py-1 font-semibold"
                          disabled={!!busy}
                          onClick={() => handleStart(c.camera_id)}
                        >
                          {busy === "starting" ? "Starting…" : "Start"}
                        </button>
                      )}
                      <button className="btn text-xs px-2 py-1" onClick={() => navigate("/calibration")}>
                        Calib
                      </button>
                      <button
                        className="btn text-xs text-cmd-crit hover:bg-cmd-crit/10 px-2 py-1"
                        disabled={!!busy}
                        onClick={() => handleDelete(c.camera_id)}
                      >
                        {busy === "deleting" ? "…" : "Del"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right side: connect live / add / upload */}
        <div className="space-y-3">
          <ConnectCamera onConnected={load} />

          <div className="panel p-3 space-y-2">
            <div className="panel-title">Add Manual Camera</div>
            <Input label="Name" v={form.name} on={(v) => setForm({ ...form, name: v })} />
            <Input label="Zone" v={form.zone} on={(v) => setForm({ ...form, zone: v })} />
            <Input label="Location" v={form.location} on={(v) => setForm({ ...form, location: v })} />
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-wider text-cmd-muted">Source Type</span>
              <select className="input text-xs" value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value })}>
                <option value="file">Video File</option>
                <option value="rtsp">RTSP Stream</option>
                <option value="webcam">Webcam</option>
              </select>
            </label>
            <Input
              label={form.source_type === "rtsp" ? "RTSP URL" : "Source Path / Device Index"}
              v={form.source_uri}
              on={(v) => setForm({ ...form, source_uri: v })}
            />
            <button className="btn btn-primary w-full text-xs font-semibold py-1.5" onClick={add}>
              Add Camera
            </button>
          </div>

          <div className="panel p-3 space-y-2">
            <div className="panel-title">Upload Video</div>
            <input
              ref={fileRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
            <button className="btn w-full text-xs py-1.5" disabled={uploading} onClick={() => fileRef.current?.click()}>
              {uploading ? "Uploading…" : "Choose video file"}
            </button>
            <p className="text-[11px] text-cmd-muted">Creates a camera from an uploaded clip (mp4/avi/mov/mkv/webm).</p>
          </div>

          {msg && (
            <div
              className={`p-2.5 rounded text-xs border ${
                msg.startsWith("✓")
                  ? "bg-cmd-ok/10 border-cmd-ok/30 text-cmd-ok"
                  : msg.startsWith("❌") || msg.toLowerCase().includes("error")
                  ? "bg-cmd-crit/10 border-cmd-crit/30 text-cmd-crit"
                  : "bg-cmd-panel2 border-cmd-border text-cmd-accent"
              }`}
            >
              {msg}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Input({ label, v, on }: { label: string; v: string; on: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-cmd-muted">{label}</span>
      <input className="input text-xs" value={v} onChange={(e) => on(e.target.value)} />
    </label>
  );
}
