import type { Comparator } from "./types";

export interface SensorMeta {
  label: string;
  unit: string;
  color: string;
}

const SENSOR_META: Record<string, SensorMeta> = {
  temperature: { label: "Temperature", unit: "°C", color: "#fb7185" },
  humidity: { label: "Humidity", unit: "%", color: "#38bdf8" },
  battery: { label: "Battery", unit: "%", color: "#34d399" },
  speed: { label: "Speed", unit: "m/s", color: "#a78bfa" },
  rssi: { label: "WiFi RSSI", unit: "dBm", color: "#f59e0b" },
  uptime_s: { label: "Uptime", unit: "s", color: "#94a3b8" },
  free_heap: { label: "Free heap", unit: "B", color: "#22d3ee" },
};

export function sensorMeta(name: string): SensorMeta {
  return SENSOR_META[name] ?? { label: name, unit: "", color: "#64748b" };
}

export function formatValue(name: string, value: number): string {
  const { unit } = sensorMeta(name);
  const rounded = Math.abs(value) >= 100 ? Math.round(value) : Math.round(value * 100) / 100;
  return unit ? `${rounded} ${unit}` : `${rounded}`;
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatRelative(iso: string | null): string {
  if (!iso) return "no data yet";
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 0) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export const COMPARATOR_LABEL: Record<Comparator, string> = {
  lt: "<",
  lte: "≤",
  gt: ">",
  gte: "≥",
};
