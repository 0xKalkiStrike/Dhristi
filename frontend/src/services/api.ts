import type {
  Analytics, Camera, Health, Journey, PipelineStatus, PlateRead,
  SpeedEvent, TrafficEvent, Vehicle, VehicleDetail,
} from "../types";

const BASE = import.meta.env.VITE_API_BASE || "";

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  health: () => req<Health>("/api/system/health"),
  runtime: () => req<any>("/api/system/runtime"),
  pipelines: () => req<{ active: number; pipelines: PipelineStatus[] }>("/api/system/pipelines"),

  cameras: () => req<Camera[]>("/api/cameras"),
  camera: (id: string) => req<Camera>(`/api/cameras/${id}`),
  createCamera: (data: Partial<Camera>) =>
    req<Camera>("/api/cameras", { method: "POST", body: JSON.stringify(data) }),
  updateCamera: (id: string, data: Partial<Camera>) =>
    req<Camera>(`/api/cameras/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteCamera: (id: string) => req(`/api/cameras/${id}`, { method: "DELETE" }),
  startCamera: (id: string, loop = true, detector?: string) =>
    req(`/api/cameras/${id}/start?loop=${loop}${detector ? `&detector=${detector}` : ""}`, { method: "POST" }),
  stopCamera: (id: string) => req(`/api/cameras/${id}/stop`, { method: "POST" }),

  calibration: (id: string) => req<any>(`/api/calibration/${id}`),
  saveCalibration: (id: string, data: any) =>
    req(`/api/calibration/${id}`, { method: "POST", body: JSON.stringify(data) }),
  testCalibration: (id: string, track?: any) =>
    req<any>(`/api/calibration/${id}/test`, { method: "POST", body: JSON.stringify(track ?? null) }),

  vehicles: (limit = 100) => req<Vehicle[]>(`/api/vehicles?limit=${limit}`),
  vehicleDetail: (uid: string) => req<VehicleDetail>(`/api/vehicles/${uid}`),
  vehicleJourney: (uid: string) => req<Journey>(`/api/vehicles/${uid}/journey`),
  search: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && qs.set(k, String(v)));
    return req<{ count: number; results: any[] }>(`/api/vehicles/search?${qs.toString()}`);
  },

  speedEvents: (limit = 50, onlyViolations = false) =>
    req<SpeedEvent[]>(`/api/speed-events?limit=${limit}&only_violations=${onlyViolations}`),
  trafficEvents: (limit = 50) => req<TrafficEvent[]>(`/api/traffic-events?limit=${limit}`),
  plateReads: (limit = 50) => req<PlateRead[]>(`/api/plate-reads?limit=${limit}`),
  analytics: (hours = 24) => req<Analytics>(`/api/analytics/summary?hours=${hours}`),
  alerts: (limit = 50) => req<any[]>(`/api/alerts?limit=${limit}`),
  auditLogs: (limit = 100) => req<any[]>(`/api/audit-logs?limit=${limit}`),

  startDemo: () => req<any>("/api/demo/start", { method: "POST" }),
  stopDemo: () => req<any>("/api/demo/stop", { method: "POST" }),
  setupDemo: () => req<any>("/api/demo/setup", { method: "POST" }),

  // live camera devices + networking
  videoDevices: () => req<any>("/api/devices/video"),
  bluetoothDevices: () => req<any>("/api/devices/bluetooth"),
  probeDevice: (index: number) => req<any>(`/api/devices/probe?index=${index}`),
  connectLive: (payload: any) =>
    req<Camera>("/api/devices/connect", { method: "POST", body: JSON.stringify(payload) }),
  network: () => req<any>("/api/system/network"),
  mongoStatus: () => req<any>("/api/mongo/status"),
};

export function frameUrl(cameraId: string): string {
  return `${BASE}/api/cameras/${cameraId}/frame.jpg`;
}
export function streamUrl(cameraId: string): string {
  return `${BASE}/api/cameras/${cameraId}/stream`;
}

export function calibFrameUrl(cameraId: string, index = 0): string {
  return `${BASE}/api/calibration/${cameraId}/frame.jpg?index=${index}`;
}
export function assetUrl(path: string): string {
  if (!path) return "";
  return `${BASE}/${path.replace(/\\/g, "/")}`;
}
