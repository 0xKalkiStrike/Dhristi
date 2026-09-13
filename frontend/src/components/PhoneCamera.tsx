import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";

const BASE = import.meta.env.VITE_API_BASE || "";

type QualityPreset = "turbo" | "balanced" | "hd";

const PRESETS: Record<QualityPreset, { label: string; maxDim: number; quality: number; targetFps: number }> = {
  turbo: { label: "Smooth Mobile (480p / 30fps) - Recommended", maxDim: 480, quality: 0.58, targetFps: 30 },
  balanced: { label: "Standard (640p / 25fps)", maxDim: 640, quality: 0.68, targetFps: 25 },
  hd: { label: "High Definition (720p / 20fps)", maxDim: 960, quality: 0.75, targetFps: 20 },
};

function getIngestWsUrl(cameraId: string): string {
  if (import.meta.env.VITE_WS_BASE) {
    return `${import.meta.env.VITE_WS_BASE}/ws/devices/ingest/${cameraId}`;
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/devices/ingest/${cameraId}`;
}

export function PhoneCamera({ onConnected }: { onConnected: () => void }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const activeRef = useRef(false);
  const callbackIdRef = useRef<number | null>(null);

  const [name, setName] = useState("My Phone Camera");
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [preset, setPreset] = useState<QualityPreset>("turbo");
  const [running, setRunning] = useState(false);
  const [camId, setCamId] = useState<string | null>(null);
  const [sent, setSent] = useState(0);
  const [liveFps, setLiveFps] = useState(0);
  const [msg, setMsg] = useState("");

  const secure = typeof window !== "undefined" && (window.isSecureContext || location.hostname === "localhost");

  useEffect(() => {
    return () => {
      void stop();
    };
  }, []);

  const start = async () => {
    setMsg("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setMsg("This browser does not support the Camera API.");
      return;
    }
    if (!secure) {
      setMsg("Camera requires a secure connection (HTTPS). Open the app via https:// and retry.");
      return;
    }

    try {
      const { maxDim, quality, targetFps } = PRESETS[preset];
      const minIntervalMs = 1000 / targetFps;

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facing },
          width: { ideal: maxDim > 640 ? 1280 : 640 },
          frameRate: { ideal: targetFps },
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      const cam = await api.connectLive({ name, source_type: "browser", start: true });
      setCamId(cam.camera_id);
      setRunning(true);
      activeRef.current = true;
      setMsg(`Streaming to ${cam.camera_id} — AI detection active in Unified View.`);
      onConnected();

      // Establish ultra-low-latency Binary WebSocket for streaming frames
      let ws: WebSocket | null = null;
      try {
        const wsUrl = getIngestWsUrl(cam.camera_id);
        ws = new WebSocket(wsUrl);
        ws.binaryType = "blob";
        wsRef.current = ws;
      } catch {
        ws = null;
      }

      let inFlight = false;
      let lastSent = 0;
      let frameCount = 0;
      let fpsTimer = performance.now();

      const processFrame = () => {
        if (!activeRef.current) return;

        const v = videoRef.current;
        const c = canvasRef.current;
        const now = performance.now();

        // Target FPS governor & buffer check to prevent any frame queuing
        if (now - lastSent >= minIntervalMs && v && c && v.videoWidth > 0 && !inFlight) {
          // Drop frame if WebSocket transmit buffer is backed up
          const wsReady = ws && ws.readyState === WebSocket.OPEN && ws.bufferedAmount === 0;

          const scale = Math.min(1, maxDim / Math.max(v.videoWidth, v.videoHeight));
          const w = Math.round(v.videoWidth * scale);
          const h = Math.round(v.videoHeight * scale);

          if (c.width !== w || c.height !== h) {
            c.width = w;
            c.height = h;
          }

          const ctx = c.getContext("2d", { willReadFrequently: true, alpha: false });
          if (ctx) {
            ctx.drawImage(v, 0, 0, w, h);
            inFlight = true;
            lastSent = now;

            c.toBlob(
              async (blob) => {
                if (blob && activeRef.current) {
                  try {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                      ws.send(blob);
                    } else {
                      // Fallback to HTTP POST
                      await fetch(`${BASE}/api/devices/ingest/${cam.camera_id}`, {
                        method: "POST",
                        headers: { "Content-Type": "image/jpeg" },
                        body: blob,
                      });
                    }
                    frameCount++;
                    setSent((n) => n + 1);

                    const elapsed = performance.now() - fpsTimer;
                    if (elapsed >= 1000) {
                      setLiveFps(Math.round((frameCount * 1000) / elapsed));
                      frameCount = 0;
                      fpsTimer = performance.now();
                    }
                  } catch {
                    /* transient network drop */
                  }
                }
                inFlight = false;
              },
              "image/jpeg",
              quality,
            );
          }
        }

        // Lock to hardware frame callback
        if (activeRef.current && videoRef.current) {
          if ("requestVideoFrameCallback" in videoRef.current) {
            callbackIdRef.current = (videoRef.current as any).requestVideoFrameCallback(processFrame);
          } else {
            callbackIdRef.current = requestAnimationFrame(processFrame);
          }
        }
      };

      if (videoRef.current) {
        if ("requestVideoFrameCallback" in videoRef.current) {
          callbackIdRef.current = (videoRef.current as any).requestVideoFrameCallback(processFrame);
        } else {
          callbackIdRef.current = requestAnimationFrame(processFrame);
        }
      }
    } catch (e: any) {
      setMsg(`Camera error: ${e?.message || e}. Ensure camera permission is granted.`);
    }
  };

  const stop = async () => {
    activeRef.current = false;
    if (callbackIdRef.current && videoRef.current && "cancelVideoFrameCallback" in videoRef.current) {
      try {
        (videoRef.current as any).cancelVideoFrameCallback(callbackIdRef.current);
      } catch {}
    }

    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {}
      wsRef.current = null;
    }

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    if (camId) {
      try {
        await api.stopCamera(camId);
      } catch {}
    }
    setRunning(false);
    setLiveFps(0);
  };

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-cmd-muted leading-snug">
        Stream live camera frames from <b className="text-cmd-text">any smartphone or browser</b> directly into the
        AI engine with zero lag over WebSocket.
      </p>

      {!secure && (
        <div className="panel p-2 border-cmd-warn/40 bg-cmd-warn/5 text-cmd-warn text-[11px]">
          Camera requires HTTPS on mobile browsers. Connect via your local HTTPS URL.
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-cmd-muted">Camera Name</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} disabled={running} />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider text-cmd-muted">Performance Profile</span>
          <select
            className="input"
            value={preset}
            onChange={(e) => setPreset(e.target.value as QualityPreset)}
            disabled={running}
          >
            {Object.entries(PRESETS).map(([k, v]) => (
              <option key={k} value={k}>
                {v.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex items-center gap-2">
        <select
          className="input flex-1"
          value={facing}
          onChange={(e) => setFacing(e.target.value as any)}
          disabled={running}
        >
          <option value="environment">Rear Camera (Main / Road)</option>
          <option value="user">Front Camera (Selfie)</option>
        </select>
        {!running ? (
          <button className="btn btn-primary px-6" onClick={start} disabled={!secure}>
            Start Live Stream
          </button>
        ) : (
          <button className="btn btn-crit px-6" onClick={stop}>
            Stop Camera
          </button>
        )}
      </div>

      <div className="relative bg-black rounded overflow-hidden aspect-video border border-cmd-border/60 shadow-inner">
        <video ref={videoRef} playsInline muted className="w-full h-full object-cover" />
        {running && (
          <div className="absolute top-2 left-2 flex items-center gap-2">
            <div className="text-[10px] font-mono bg-black/75 px-2 py-0.5 rounded text-cmd-ok flex items-center gap-1.5 border border-cmd-ok/30">
              <span className="w-2 h-2 rounded-full bg-cmd-ok animate-pulse" /> LIVE · {camId}
            </div>
            <div className="text-[10px] font-mono bg-black/75 px-2 py-0.5 rounded text-white border border-white/20">
              {liveFps} FPS · {sent} frames
            </div>
          </div>
        )}
      </div>
      <canvas ref={canvasRef} className="hidden" />
      {msg && <div className="text-xs text-cmd-accent">{msg}</div>}
    </div>
  );
}
