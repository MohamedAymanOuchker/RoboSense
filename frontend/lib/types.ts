export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface Device {
  id: number;
  name: string;
  api_key_prefix: string;
  created_at: string;
}

export interface DeviceWithKey extends Device {
  api_key: string;
}

export interface TelemetryPoint {
  time: string;
  sensor_name: string;
  value: number;
}

export interface TelemetryResult {
  device_id: number;
  sensor_name: string | null;
  bucket: string | null;
  agg: string | null;
  count: number;
  points: TelemetryPoint[];
}

export interface SensorSnapshot {
  sensor_name: string;
  value: number;
  time: string;
}

export interface LatestSnapshot {
  device_id: number;
  last_seen: string | null;
  readings: SensorSnapshot[];
}

export type Comparator = "lt" | "lte" | "gt" | "gte";

export interface AlertRule {
  id: number;
  device_id: number;
  sensor_name: string;
  comparator: Comparator;
  threshold: number;
  created_at: string;
}

export interface AlertStatus {
  rule_id: number;
  sensor_name: string;
  comparator: Comparator;
  threshold: number;
  latest_value: number | null;
  latest_time: string | null;
  triggered: boolean;
}
