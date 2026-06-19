import type {
  AlertRule,
  AlertStatus,
  Comparator,
  Device,
  DeviceWithKey,
  LatestSnapshot,
  TelemetryResult,
  User,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: string;
  token?: string | null;
  body?: unknown;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;

  const res = await fetch(`${API_URL}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // body wasn't JSON; keep the status text
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface QueryParams {
  deviceId: number;
  sensorName?: string;
  start?: string;
  end?: string;
  bucket?: string;
  agg?: string;
  order?: "asc" | "desc";
  limit?: number;
}

function buildQuery(params: QueryParams): string {
  const q = new URLSearchParams({ device_id: String(params.deviceId) });
  if (params.sensorName) q.set("sensor_name", params.sensorName);
  if (params.start) q.set("start", params.start);
  if (params.end) q.set("end", params.end);
  if (params.bucket) q.set("bucket", params.bucket);
  if (params.agg) q.set("agg", params.agg);
  if (params.order) q.set("order", params.order);
  if (params.limit) q.set("limit", String(params.limit));
  return q.toString();
}

export const api = {
  register: (email: string, password: string) =>
    request<User>("/api/auth/register", { method: "POST", body: { email, password } }),

  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/api/auth/login", {
      method: "POST",
      body: { email, password },
    }),

  me: (token: string) => request<User>("/api/auth/me", { token }),

  listDevices: (token: string) => request<Device[]>("/api/devices", { token }),

  getDevice: (token: string, id: number) => request<Device>(`/api/devices/${id}`, { token }),

  createDevice: (token: string, name: string) =>
    request<DeviceWithKey>("/api/devices", { method: "POST", token, body: { name } }),

  renameDevice: (token: string, id: number, name: string) =>
    request<Device>(`/api/devices/${id}`, { method: "PATCH", token, body: { name } }),

  deleteDevice: (token: string, id: number) =>
    request<void>(`/api/devices/${id}`, { method: "DELETE", token }),

  regenerateKey: (token: string, id: number) =>
    request<DeviceWithKey>(`/api/devices/${id}/regenerate-key`, { method: "POST", token }),

  latest: (token: string, deviceId: number) =>
    request<LatestSnapshot>(`/api/telemetry/latest?device_id=${deviceId}`, { token }),

  query: (token: string, params: QueryParams) =>
    request<TelemetryResult>(`/api/telemetry?${buildQuery(params)}`, { token }),

  listAlerts: (token: string, deviceId: number) =>
    request<AlertRule[]>(`/api/devices/${deviceId}/alerts`, { token }),

  createAlert: (
    token: string,
    deviceId: number,
    rule: { sensor_name: string; comparator: Comparator; threshold: number },
  ) =>
    request<AlertRule>(`/api/devices/${deviceId}/alerts`, {
      method: "POST",
      token,
      body: rule,
    }),

  deleteAlert: (token: string, deviceId: number, ruleId: number) =>
    request<void>(`/api/devices/${deviceId}/alerts/${ruleId}`, { method: "DELETE", token }),

  alertStatus: (token: string, deviceId: number) =>
    request<AlertStatus[]>(`/api/devices/${deviceId}/alerts/status`, { token }),
};
