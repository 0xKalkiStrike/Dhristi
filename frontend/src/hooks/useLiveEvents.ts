import { useEffect, useRef, useState } from "react";
import type { LiveEvent } from "../types";

let eventSeq = 0;
function createEventId(prefix = "evt"): string {
  eventSeq = (eventSeq + 1) % 1_000_000_000;
  return `${prefix}-${Date.now()}-${eventSeq}-${Math.random().toString(36).slice(2, 8)}`;
}

function getWsUrl(): string {
  if (import.meta.env.VITE_WS_BASE) {
    return `${import.meta.env.VITE_WS_BASE}/ws/events`;
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/events`;
}

export function useLiveEvents(max = 60) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const isConnectedRef = useRef(false);

  useEffect(() => {
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout>;
    let fallbackPollTimer: ReturnType<typeof setInterval>;

    const pushEvents = (newEvents: LiveEvent[]) => {
      setEvents((prev) => {
        const seen = new Set(
          prev.map((e: any) => e._id || (e.tracking_id ? `${e.camera_id || ""}-${e.tracking_id}` : "")).filter(Boolean),
        );
        const filtered = newEvents.filter((e: any) => {
          const key = e._id || (e.tracking_id ? `${e.camera_id || ""}-${e.tracking_id}` : "");
          return !key || !seen.has(key);
        });
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
          isConnectedRef.current = true;
          setConnected(true);
        };

        ws.onclose = () => {
          isConnectedRef.current = false;
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
            const uniqueEvent = { ...data, _id: (data as any)._id || createEventId("ws") };
            setEvents((prev) => [uniqueEvent, ...prev].slice(0, max));
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
      if (!isConnectedRef.current && !closed) {
        try {
          const res = await fetch("/api/system/events/recent?limit=15");
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
              pushEvents(data.map((d) => ({ ...d, _id: d.id ? `poll-${d.id}` : createEventId("poll") })));
            }
          }
        } catch {}
      }
    }, 2500);

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
  }, [max]);

  return { events, connected };
}
