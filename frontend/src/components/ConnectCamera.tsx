import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import { Spinner } from "./ui";

type Tab = "browser" | "webcam" | "ip" | "bluetooth";

export function ConnectCamera({ onConnected }: { onConnected: () => void }) {
  const [tab, setTab] = useState<Tab>("browser");
  const [videoDevs, setVideoDevs] = useState<any[] | null>(null);
  const [btDevs, setBtDevs] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [name, setName] = useState("Live Camera");
  const [index, setIndex] = useState(0);
  const [url, setUrl] = useState("");
  const [probe, setProbe] = useState<Record<number, any>>({});

  // Browser WebCam State
  const [streaming, setStreaming] = useState(false);
  const [activeCamId, setActiveCamId] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const pushIntervalRef = useRef<any>(null);
  const [streamFps, setStreamFps] = useState(0);

  // Clean up browser camera when unmounting
  useEffect(() => {
    return () => {
      stopBrowserStream();
    };
  }, []);

  const stopBrowserStream = () => {
    if (pushIntervalRef.current) {
      clearInterval(pushIntervalRef.current);
      pushIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setStreaming(false);
    setActiveCamId(null);
  };

  const startBrowserStream = async () => {
    setBusy(true);
    setMsg("Requesting browser camera permission…");
    try {
      // 1. Create camera in backend
      const cam = await api.connectLive({
        name: name || "Browser WebCam",
        source_type: "browser",
        start: true,
      });

      // 2. Request userMedia
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 30 },
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setActiveCamId(cam.camera_id);
      setStreaming(true);
      setMsg(`✓ Live camera ${cam.camera_id} streaming to AI engine!`);
      onConnected();

      // 3. Start frame pusher loop (hardware V-Sync locked with aspect ratio preservation)
      const canvas = canvasRef.current || document.createElement("canvas");
      const ctx = canvas.getContext("2d", { willReadFrequently: true });

      let frameCount = 0;
      let lastFpsTime = Date.now();
      let inFlight = false;
      let active = true;

      const processFrame = () => {
        if (!active) return;
        const v = videoRef.current;
        if (v && v.readyState >= 2 && ctx && !inFlight && v.videoWidth > 0) {
          const maxDim = 640;
          const scale = Math.min(1, maxDim / Math.max(v.videoWidth, v.videoHeight));
          const w = Math.round(v.videoWidth * scale);
          const h = Math.round(v.videoHeight * scale);

          if (canvas.width !== w || canvas.height !== h) {
            canvas.width = w;
            canvas.height = h;
          }

          ctx.drawImage(v, 0, 0, w, h);
          inFlight = true;
          canvas.toBlob(
            async (blob) => {
              if (blob && active) {
                try {
                  await fetch(`/api/devices/ingest/${cam.camera_id}`, {
                    method: "POST",
                    headers: { "Content-Type": "image/jpeg" },
                    body: blob,
                  });
                  frameCount++;
                  const now = Date.now();
                  if (now - lastFpsTime >= 1000) {
                    setStreamFps(frameCount);
                    frameCount = 0;
                    lastFpsTime = now;
                  }
                } catch {
                  /* transient */
                }
              }
              inFlight = false;
            },
            "image/jpeg",
            0.68,
          );
        }

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
      setMsg(`Camera error: ${e.message || e}`);
      stopBrowserStream();
    } finally {
      setBusy(false);
    }
  };

  const scanVideo = async () => {
    setBusy(true);
    setMsg("");
    try {
      const res = await api.videoDevices();
      setVideoDevs(res.devices || []);
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  const scanBt = async () => {
    setBusy(true);
    setMsg("");
    try {
      setBtDevs(await api.bluetoothDevices());
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doProbe = async (i: number) => {
    setMsg(`Probing device ${i}…`);
    try {
      const r = await api.probeDevice(i);
      setProbe((p) => ({ ...p, [i]: r }));
      setMsg(r.ok ? `✓ Device ${i}: ${r.width}x${r.height} OK` : `❌ Device ${i}: ${r.error || "unavailable"}`);
    } catch (e: any) {
      setMsg(e.message);
    }
  };

  const connect = async (payload: any) => {
    setBusy(true);
    setMsg("Connecting live camera (real detector, no demo data)…");
    try {
      const cam = await api.connectLive(payload);
      setMsg(`✓ Connected ${cam.camera_id}. Live analysis started.`);
      onConnected();
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="panel-title">Connect Live Camera</div>
        <span className="text-[10px] text-cmd-ok font-mono">REAL INPUT · ZERO LAG</span>
      </div>

      {/* Tabs */}
      <div className="grid grid-cols-4 gap-1">
        {(
          [
            { id: "browser", label: "Browser Cam" },
            { id: "webcam", label: "OS WebCam" },
            { id: "ip", label: "Phone / IP" },
            { id: "bluetooth", label: "Bluetooth" },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`btn text-[11px] px-1.5 py-1.5 truncate ${tab === t.id ? "btn-primary font-semibold" : ""}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-[10px] uppercase tracking-wider text-cmd-muted">Camera name</span>
        <input className="input text-xs" value={name} onChange={(e) => setName(e.target.value)} />
      </label>

      {/* 1. Browser WebCam */}
      {tab === "browser" && (
        <div className="space-y-2.5">
          <p className="text-[11px] text-cmd-text leading-snug">
            Stream directly from this laptop / device webcam into the DRISHTI-V engine. No OS driver configuration needed.
          </p>

          <div className="relative aspect-video bg-black rounded border border-cmd-border overflow-hidden flex items-center justify-center">
            <video ref={videoRef} className={`w-full h-full object-cover ${streaming ? "block" : "hidden"}`} playsInline muted />
            <canvas ref={canvasRef} className="hidden" />
            {!streaming && (
              <div className="text-cmd-muted text-xs flex flex-col items-center gap-1.5">
                <span className="text-2xl opacity-40">🎥</span>
                <span>Camera preview inactive</span>
              </div>
            )}
            {streaming && (
              <div className="absolute top-1.5 left-1.5 bg-black/70 px-2 py-0.5 rounded text-[10px] text-cmd-ok font-mono flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-cmd-ok animate-pulse" />
                <span>LIVE {streamFps} FPS</span>
                {activeCamId && <span className="text-cmd-accent font-bold">· {activeCamId}</span>}
              </div>
            )}
          </div>

          {!streaming ? (
            <button className="btn btn-primary w-full text-xs font-semibold py-2" onClick={startBrowserStream} disabled={busy}>
              {busy ? "Starting Camera…" : "▶ Start Browser WebCam"}
            </button>
          ) : (
            <button className="btn w-full text-xs text-cmd-crit font-semibold py-2" onClick={stopBrowserStream}>
              ■ Stop Camera Stream
            </button>
          )}
        </div>
      )}

      {/* 2. OS WebCam */}
      {tab === "webcam" && (
        <div className="space-y-2">
          <button className="btn w-full text-xs" onClick={scanVideo} disabled={busy}>
            Scan OS Cameras
          </button>
          {busy && !videoDevs && <Spinner label="Scanning devices…" />}
          {videoDevs && videoDevs.length === 0 && <p className="text-xs text-cmd-muted">No OS cameras found.</p>}
          {videoDevs?.map((d) => (
            <div key={d.index} className="flex items-center justify-between gap-2 border border-cmd-border rounded p-2">
              <div className="min-w-0">
                <div className="text-xs font-medium text-white truncate">{d.name}</div>
                <div className="text-[10px] text-cmd-muted font-mono">
                  Index {d.index}
                  {d.is_bluetooth ? " · Bluetooth" : ""}
                  {probe[d.index]
                    ? probe[d.index].ok
                      ? ` · ${probe[d.index].width}x${probe[d.index].height} OK`
                      : " · probe failed"
                    : ""}
                </div>
              </div>
              <div className="flex gap-1 shrink-0">
                <button className="btn text-xs py-1 px-2" onClick={() => doProbe(d.index)}>
                  Probe
                </button>
                <button
                  className="btn btn-primary text-xs py-1 px-2"
                  disabled={busy}
                  onClick={() =>
                    connect({
                      name,
                      source_type: d.is_bluetooth ? "bluetooth" : "webcam",
                      index: d.index,
                      start: true,
                    })
                  }
                >
                  Connect
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 3. Phone / IP */}
      {tab === "ip" && (
        <div className="space-y-2">
          <p className="text-[11px] text-cmd-muted leading-snug">
            Connect an IP camera or smartphone (e.g. <i>IP Webcam</i> app). Enter the RTSP or HTTP video stream URL:
          </p>
          <input
            className="input w-full font-mono text-xs"
            placeholder="rtsp://192.168.1.9:8080/h264 or http://..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button
            className="btn btn-primary w-full text-xs py-1.5"
            disabled={busy || !url.trim()}
            onClick={() => connect({ name, source_type: "rtsp", url: url.trim(), start: true })}
          >
            Connect &amp; Start
          </button>
        </div>
      )}

      {/* 4. Bluetooth */}
      {tab === "bluetooth" && (
        <div className="space-y-2">
          <button className="btn w-full text-xs" onClick={scanBt} disabled={busy}>
            Scan Bluetooth
          </button>
          {busy && !btDevs && <Spinner />}
          {btDevs && (
            <>
              <p className="text-[11px] text-cmd-warn leading-snug">{btDevs.note}</p>
              {btDevs.devices?.map((d: any, i: number) => (
                <div key={i} className="flex items-center justify-between border border-cmd-border rounded p-2">
                  <div className="text-xs text-white truncate">
                    {d.name}
                    {d.looks_like_camera && <span className="ml-1 text-[10px] text-cmd-ok font-mono">camera</span>}
                    {d.is_adapter && <span className="ml-1 text-[10px] text-cmd-muted font-mono">adapter</span>}
                  </div>
                </div>
              ))}
              <div className="border-t border-cmd-border pt-2 space-y-2">
                <p className="text-[11px] text-cmd-muted">Device index after pairing:</p>
                <div className="flex gap-2">
                  <input
                    className="input w-20 text-xs"
                    type="number"
                    min={0}
                    value={index}
                    onChange={(e) => setIndex(Number(e.target.value))}
                  />
                  <button className="btn text-xs" onClick={() => doProbe(index)}>
                    Probe
                  </button>
                  <button
                    className="btn btn-primary text-xs flex-1"
                    disabled={busy}
                    onClick={() => connect({ name, source_type: "bluetooth", index, start: true })}
                  >
                    Connect
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {msg && (
        <div className={`p-2 rounded text-xs border ${msg.startsWith("✓") ? "bg-cmd-ok/10 border-cmd-ok/30 text-cmd-ok" : msg.startsWith("❌") || msg.toLowerCase().includes("error") ? "bg-cmd-crit/10 border-cmd-crit/30 text-cmd-crit" : "bg-cmd-panel2 border-cmd-border text-cmd-accent"}`}>
          {msg}
        </div>
      )}
    </div>
  );
}
