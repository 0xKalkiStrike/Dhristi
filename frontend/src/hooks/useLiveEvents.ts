import { useEffect, useRef, useState } from "react";
import type { LiveEvent } from "../types";

const WS_BASE =
  import.meta.env.VITE_WS_BASE ||
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

export function useLiveEvents(max = 60) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      try {
        const ws = new WebSocket(`${WS_BASE}/ws/events`);
        wsRef.current = ws;
        ws.onopen = () => setConnected(true);
        ws.onclose = () => {
          setConnected(false);
          if (!closed) retry = setTimeout(connect, 2000);
        };
        ws.onerror = () => {
          // let onclose handle reconnection without aborting connection abruptly
        };
        ws.onmessage = (msg) => {
          try {
            const data = JSON.parse(msg.data) as LiveEvent;
            if (data.type === "connected") return;
            setEvents((prev) => [{ ...data, _id: Date.now() + Math.random() }, ...prev].slice(0, max));
          } catch {
            /* ignore malformed */
          }
        };
      } catch {
        if (!closed) retry = setTimeout(connect, 2500);
      }
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      const ws = wsRef.current;
      if (ws) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        } else if (ws.readyState === WebSocket.CONNECTING) {
          ws.onopen = () => ws.close();
        }
      }
    };
  }, [max]);


  return { events, connected };
}
