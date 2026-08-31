import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";

const BASE = import.meta.env.VITE_API_BASE || "";
const SEND_MS = 50;       // ~20 fps upload for smooth real-time stream
const MAX_W = 640;        // cap upload width for performance

export function PhoneCamera({ onConnected }: { onConnected: () => void }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [name, setName] = useState("My Phone Camera");
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [running, setRunning] = useState(false);
  const [camId, setCamId] = useState<string | null>(null);
  const [sent, setSent] = useState(0);
  const [msg, setMsg] = useState("");

  const secure = typeof window !== "undefined" && (window.isSecureContext || location.hostname === "localhost");

  useEffect(() => {
    return () => {
      void stop();
    };
  }, []); // cleanup on unmount


  const start = async () => {
    setMsg("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setMsg("This browser has no camera API."); return;
    }
    if (!secure) {
      setMsg("Camera needs a secure page (HTTPS). Open the app via its https:// address (see below), then retry.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facing }, width: { ideal: 1280 } }, audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }

      const cam = await api.connectLive({ name, source_type: "browser", start: true });
      setCamId(cam.camera_id);
      setRunning(true);
      setMsg(`Streaming to ${cam.camera_id} — open Unified View to see live detection.`);
      onConnected();

      let inFlight = false;
      let active = true;

      const processFrame = () => {
        if (!active) return;
        const v = videoRef.current;
        const c = canvasRef.current;
        if (v && c && v.videoWidth > 0 && !inFlight) {
          const maxDim = 640;
          const scale = Math.min(1, maxDim / Math.max(v.videoWidth, v.videoHeight));
          const w = Math.round(v.videoWidth * scale);
          const h = Math.round(v.videoHeight * scale);
          if (c.width !== w || c.height !== h) {
            c.width = w;
            c.height = h;
          }
          const ctx = c.getContext("2d", { willReadFrequently: true });
          if (ctx) {
            ctx.drawImage(v, 0, 0, w, h);
            inFlight = true;
            c.toBlob(
              async (blob) => {
                if (blob && active) {
                  try {
                    await fetch(`${BASE}/api/devices/ingest/${cam.camera_id}`, {
                      method: "POST",
                      headers: { "Content-Type": "image/jpeg" },
                      body: blob,
                    });
                    setSent((n) => n + 1);
                  } catch {
                    /* transient */
                  }
                }
                inFlight = false;
              },
              "image/jpeg",
              0.65
            );
          }
        }

        // Hardware V-Sync locked next frame callback
        if (active && videoRef.current) {
          if ("requestVideoFrameCallback" in videoRef.current) {
            (videoRef.current as any).requestVideoFrameCallback(processFrame);
          } else {
            requestAnimationFrame(processFrame);
          }
        }
      };

      if (videoRef.current) {
        if ("requestVideoFrameCallback" in videoRef.current) {
          (videoRef.current as any).requestVideoFrameCallback(processFrame);
        } else {
          requestAnimationFrame(processFrame);
        }
      }
    } catch (e: any) {
      setMsg(`Camera error: ${e?.message || e}. Grant camera permission and use HTTPS.`);
    }
  };

  const stop = async () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (camId) { try { await api.stopCamera(camId); } catch { /* ignore */ } }
    setRunning(false);
  };

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-cmd-muted leading-snug">
        Use <b className="text-cmd-text">this phone's own camera</b>. Frames are captured in the
        browser and sent to the backend for live YOLO analysis — no separate app.
      </p>

      {!secure && (
        <div className="panel p-2 border-cmd-warn/40 bg-cmd-warn/5 text-cmd-warn text-[11px]">
          Camera needs a secure (HTTPS) page. Serve the app over HTTPS
          (<span className="font-mono">scripts\setup\run_https.ps1</span>) and open its
          <span className="font-mono"> https://&lt;ip&gt;:8443</span> address on the phone.
        </div>
      )}

      <label className="flex flex-col gap-1">
        <span className="text-[10px] uppercase tracking-wider text-cmd-muted">Camera name</span>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} disabled={running} />
      </label>

      <div className="flex items-center gap-2">
        <select className="input" value={facing} onChange={(e) => setFacing(e.target.value as any)} disabled={running}>
          <option value="environment">Rear camera</option>
          <option value="user">Front camera</option>
        </select>
        {!running ? (
          <button className="btn btn-primary flex-1" onClick={start} disabled={!secure}>Use This Camera</button>
        ) : (
          <button className="btn flex-1" onClick={stop}>Stop</button>
        )}
      </div>

      <div className="relative bg-black rounded overflow-hidden aspect-video">
        <video ref={videoRef} playsInline muted className="w-full h-full object-cover" />
        {running && (
          <div className="absolute top-1 left-1 text-[10px] bg-black/60 px-1.5 py-0.5 rounded text-cmd-ok">
            ● LIVE · {camId} · {sent} frames sent
          </div>
        )}
      </div>
      <canvas ref={canvasRef} className="hidden" />
      {msg && <div className="text-xs text-cmd-accent">{msg}</div>}
    </div>
  );
}
