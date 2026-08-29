import { useEffect, useState } from "react";
import { frameUrl, streamUrl } from "../services/api";
import type { Camera, PipelineStatus } from "../types";
import { LiveDot } from "./ui";

const ENV_TONE: Record<string, string> = {
  day: "text-cmd-ok",
  fog: "text-cmd-warn",
  night: "text-cmd-accent2",
  low_light: "text-cmd-accent2",
  rain: "text-cmd-accent2",
  blur: "text-cmd-warn",
  overexposed: "text-cmd-warn",
  unknown: "text-cmd-muted",
};

export function CameraTile({
  camera, status, onClick,
}: { camera: Camera; status?: PipelineStatus; onClick?: () => void }) {
  const online = status?.running || camera.status === "online";
  const [retries, setRetries] = useState(0);
  const [useFallback, setUseFallback] = useState(false);

  // If stream gets interrupted, try to reconnect up to 3 times, then fall back to snapshot
  const handleError = () => {
    if (retries < 3) {
      setTimeout(() => {
        setRetries((r) => r + 1);
      }, 2000);
    } else {
      setUseFallback(true);
    }
  };

  const env = status?.environment || camera.last_environment || "unknown";
  const imgSrc = useFallback
    ? `${frameUrl(camera.camera_id)}?t=${retries}`
    : `${streamUrl(camera.camera_id)}?r=${retries}`;

  return (
    <button
      onClick={onClick}
      className="panel overflow-hidden text-left group hover:border-cmd-accent/50 transition-colors"
    >
      <div className="relative bg-black aspect-video flex items-center justify-center scanline">
        {online ? (
          <img
            key={`${camera.camera_id}-${useFallback ? "fb" : "st"}-${retries}`}
            src={imgSrc}
            alt={camera.name}
            className="w-full h-full object-cover transition-opacity duration-300"
            onError={handleError}
          />
        ) : (
          <div className="text-cmd-muted text-xs flex flex-col items-center gap-1">
            <span className="text-2xl opacity-40">▣</span>
            NO SIGNAL
          </div>
        )}


        <div className="absolute top-1 left-1 right-1 flex items-center justify-between text-[10px]">
          <span className="bg-black/60 px-1.5 py-0.5 rounded flex items-center gap-1">
            <LiveDot on={online} /> {camera.camera_id}
          </span>
          <span className={`bg-black/60 px-1.5 py-0.5 rounded uppercase ${ENV_TONE[env] || "text-cmd-muted"}`}>
            {env}
          </span>
        </div>
        {online && (
          <div className="absolute bottom-1 left-1 right-1 flex items-center justify-between text-[10px] text-cmd-text">
            <span className="bg-black/60 px-1.5 py-0.5 rounded">{status?.tracks ?? 0} tracked</span>
            <span className="bg-black/60 px-1.5 py-0.5 rounded font-mono">{(status?.fps ?? camera.fps).toFixed(0)} fps</span>
          </div>
        )}
      </div>
      <div className="p-2 flex items-center justify-between">
        <div className="min-w-0">
          <div className="text-sm font-medium text-white truncate">{camera.name}</div>
          <div className="text-[11px] text-cmd-muted truncate">{camera.zone} · {camera.location || "—"}</div>
        </div>
        <div className="text-right text-[10px] text-cmd-muted shrink-0">
          {camera.has_calibration ? (
            <span className="text-cmd-ok">CAL ✓</span>
          ) : (
            <span className="text-cmd-warn">NO CAL</span>
          )}
        </div>
      </div>
    </button>
  );
}
