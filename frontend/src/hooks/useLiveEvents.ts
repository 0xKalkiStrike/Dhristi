import { useEffect, useRef, useState } from "react";
import type { LiveEvent } from "../types";

function getWsUrl(): string {
  if (import.meta.env.VITE_WS_BASE) {
    return `${import.meta.env.VITE_WS_BASE}/ws/events`;
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  // Always connect directly to FastAPI backend on port 8000
  const host = location.port === "5173" ? `${location.hostname}:8000` : location.host;
  return `${proto}://${host}/ws/events`;
}

export function useLiveEvents(max = 60) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout>;
    let fallbackPollTimer: ReturnType<typeof setInterval>;
    let attempts = 0;

    const pushEvents = (newEvents: LiveEvent[]) => {
      setEvents((prev) => {
        const seen = new Set(prev.map((e: any) => e.tracking_id || e._id));
        const filtered = newEvents.filter((e: any) => !seen.has(e.tracking_id || e._id));
        return [...filtered, ...prev].slice(0, max);
      });
    };

    const connect = () => {
      if (closed) return;
      const url = getWsUrl();
      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          setConnected(true);
        };

        ws.onclose = () => {
          setConnected(false);
          if (!closed) {
            retryTimer = setTimeout(connect, 3000);
          }
        };

        ws.onerror = () => {
          // Handled via onclose
        };

        ws.onmessage = (msg) => {
          try {
            const data = JSON.parse(msg.data) as LiveEvent;
            if (data.type === "connected") return;
            setEvents((prev) => [{ ...data, _id: Date.now() + Math.random() }, ...prev].slice(0, max));
          } catch {}
        };
      } catch {
        if (!closed) {
          retryTimer = setTimeout(connect, 3000);
        }
      }
    };

    connect();

    // High-frequency telemetry polling fallback (active when WS is disconnected)
    fallbackPollTimer = setInterval(async () => {
      if (!connected && !closed) {
        try {
          const res = await fetch("/api/system/events/recent?limit=15");
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
              pushEvents(data.map((d) => ({ ...d, _id: d.id || Date.now() + Math.random() })));
            }
          }
        } catch {}
      }
    }, 2000);

    return () => {
      closed = true;
      clearTimeout(retryTimer);
      clearInterval(fallbackPollTimer);
      const ws = wsRef.current;
      if (ws) {
        try {
          if (ws.readyState === WebSocket.OPEN) {
            ws.close();
          } else if (ws.readyState === WebSocket.CONNECTING) {
            ws.onopen = () => ws.close();
          }
        } catch {}
      }
    };
  }, [max, connected]);

  return { events, connected };
}
