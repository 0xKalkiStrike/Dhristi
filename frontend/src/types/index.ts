export interface Health {
  status: string;
  version: string;
  ai_runtime: string;
  detector_backend: string;
  ocr_engine: string;
  device: string;
  database: string;
  mongo_enabled?: boolean;
  mongo_connected?: boolean;
  cuda_available: boolean;
  active_pipelines: number;
  uptime_seconds: number;
}

export interface Camera {
  id: number;
  camera_id: string;
  name: string;
  location: string;
  zone: string;
  orientation: string;
  source_type: string;
  has_source: boolean;
  latitude: number | null;
  longitude: number | null;
  enabled: boolean;
  status: string;
  fps: number;
  last_environment: string;
  ai_status: string;
  has_calibration: boolean;
}

export interface PipelineStatus {
  camera_id: string;
  running: boolean;
  error: string | null;
  frames: number;
  detections: number;
  fps: number;
  tracks: number;
  plates: number;
  speed_events: number;
  traffic_events: number;
  environment: string;
  backend: string;
  inference_ms: number;
}

export interface Vehicle {
  id: number;
  vehicle_uid: string;
  plate_number: string | null;
  vehicle_class: string;
  color: string;
  plate_confidence: number;
  first_seen: string;
  last_seen: string;
  observation_count: number;
}

export interface SpeedEvent {
  id: number;
  camera_id: string;
  tracking_id: string | null;
  vehicle_uid: string | null;
  plate_number: string | null;
  distance_m: number;
  elapsed_s: number;
  speed_kmh: number;
  speed_limit_kmh: number;
  excess_kmh: number;
  method: string;
  confidence: number;
  is_violation: boolean;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface TrafficEvent {
  id: number;
  event_type: string;
  camera_id: string;
  tracking_id: string | null;
  vehicle_uid: string | null;
  plate_number: string | null;
  severity: string;
  confidence: number;
  reason: string;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface PlateRead {
  id: number;
  camera_id: string;
  vehicle_uid: string | null;
  raw_text: string;
  normalized_text: string;
  confidence: number;
  ocr_engine: string;
  valid_format: boolean;
  needs_verification: boolean;
  crop_path: string;
  timestamp: string;
}

export interface Journey {
  id: number;
  vehicle_uid: string;
  plate_number: string | null;
  first_camera: string;
  last_camera: string;
  first_seen: string;
  last_seen: string;
  hop_count: number;
  path: { camera_id: string; timestamp: string; speed_kmh: number | null }[];
  association_confidence: number;
}

export interface VehicleDetail {
  vehicle: Vehicle;
  observations: any[];
  journey: Journey | null;
  speed_events: SpeedEvent[];
  plate_reads: PlateRead[];
}

export interface Analytics {
  vehicles_detected: number;
  average_speed_kmh: number;
  max_speed_kmh: number;
  overspeed_events: number;
  anpr_reads: number;
  cameras_online: number;
  cameras_total: number;
  camera_uptime_pct: number;
  violations_by_hour: Record<string, number>;
  violations_by_camera: Record<string, number>;
  vehicle_categories: Record<string, number>;
  speed_distribution: Record<string, number>;
  speed_samples: number;
}

export interface LiveEvent {
  type: string;
  camera_id?: string;
  timestamp?: string;
  [key: string]: any;
}
