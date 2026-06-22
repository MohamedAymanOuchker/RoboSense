"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useMemo, useState } from "react";

import { AlertsPanel } from "@/components/AlertsPanel";
import { ApiKeyDialog } from "@/components/ApiKeyDialog";
import { SensorChart, type SeriesPoint } from "@/components/SensorChart";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatRelative, formatValue, sensorMeta } from "@/lib/format";
import type {
  AlertStatus,
  AnomalyPoint,
  Device,
  DeviceWithKey,
  LatestSnapshot,
} from "@/lib/types";
import { useDeviceStream } from "@/lib/useDeviceStream";

// z-score threshold for the dashboard's anomaly markers (configurable on the API).
const ANOMALY_Z = 5;

// Short ranges query raw telemetry with on-the-fly time_bucket; long ranges
// (24h/7d) read the pre-materialized hourly continuous aggregate.
const RANGES = {
  "1h": { label: "1h", ms: 3_600_000, bucket: "1m", summary: false },
  "6h": { label: "6h", ms: 21_600_000, bucket: "5m", summary: false },
  "24h": { label: "24h", ms: 86_400_000, bucket: "15m", summary: true },
  "7d": { label: "7d", ms: 604_800_000, bucket: "1h", summary: true },
} as const;

type RangeKey = keyof typeof RANGES;

const SENSOR_ORDER = ["battery", "temperature", "humidity", "speed", "rssi", "free_heap", "uptime_s"];

function orderSensors(names: string[]): string[] {
  return [...names].sort((a, b) => {
    const ia = SENSOR_ORDER.indexOf(a);
    const ib = SENSOR_ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib) || a.localeCompare(b);
  });
}

export default function DeviceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const deviceId = Number(id);
  const { token } = useAuth();
  const router = useRouter();

  const [device, setDevice] = useState<Device | null>(null);
  const [latest, setLatest] = useState<LatestSnapshot | null>(null);
  const [series, setSeries] = useState<Record<string, SeriesPoint[]>>({});
  const [anomalies, setAnomalies] = useState<Record<string, AnomalyPoint[]>>({});
  const [domain, setDomain] = useState<[number, number] | undefined>(undefined);
  const [alerts, setAlerts] = useState<AlertStatus[]>([]);
  const [range, setRange] = useState<RangeKey>("6h");
  const [rotatedKey, setRotatedKey] = useState<DeviceWithKey | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .getDevice(token, deviceId)
      .then(setDevice)
      .catch(() => setNotFound(true));
  }, [token, deviceId]);

  const loadTelemetry = useCallback(async () => {
    if (!token) return;
    const end = new Date();
    const start = new Date(end.getTime() - RANGES[range].ms);
    const telemetry = RANGES[range].summary
      ? api.summary(token, {
          deviceId,
          agg: "avg",
          order: "asc",
          start: start.toISOString(),
          end: end.toISOString(),
        })
      : api.query(token, {
          deviceId,
          bucket: RANGES[range].bucket,
          agg: "avg",
          order: "asc",
          start: start.toISOString(),
          end: end.toISOString(),
          limit: 5000,
        });
    const [snap, result, status] = await Promise.all([
      api.latest(token, deviceId),
      telemetry,
      api.alertStatus(token, deviceId),
    ]);
    const grouped: Record<string, SeriesPoint[]> = {};
    for (const p of result.points) {
      (grouped[p.sensor_name] ??= []).push({ time: p.time, value: p.value });
    }
    setLatest(snap);
    setSeries(grouped);
    setAlerts(status);
    setDomain([start.getTime(), end.getTime()]);

    // Anomaly markers per sensor over the same range.
    const names = [
      ...new Set([...Object.keys(grouped), ...snap.readings.map((r) => r.sensor_name)]),
    ];
    const results = await Promise.all(
      names.map((name) =>
        api
          .anomalies(token, {
            deviceId,
            sensorName: name,
            start: start.toISOString(),
            end: end.toISOString(),
            z: ANOMALY_Z,
          })
          .catch(() => null),
      ),
    );
    const anomalyMap: Record<string, AnomalyPoint[]> = {};
    names.forEach((name, i) => {
      if (results[i]) anomalyMap[name] = results[i]!.anomalies;
    });
    setAnomalies(anomalyMap);
  }, [token, deviceId, range]);

  useEffect(() => {
    loadTelemetry().catch(() => {});
    const interval = setInterval(() => loadTelemetry().catch(() => {}), 5000);
    return () => clearInterval(interval);
  }, [loadTelemetry]);

  const sensorNames = useMemo(() => {
    const names = new Set<string>([
      ...Object.keys(series),
      ...(latest?.readings.map((r) => r.sensor_name) ?? []),
    ]);
    return orderSensors([...names]);
  }, [series, latest]);

  const { reading: liveReading, connected: live } = useDeviceStream(deviceId);

  // Current readings: the latest snapshot with any live-streamed reading on top.
  const liveValues = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of latest?.readings ?? []) map.set(r.sensor_name, r.value);
    if (liveReading) for (const [k, v] of Object.entries(liveReading.readings)) map.set(k, v);
    return map;
  }, [latest, liveReading]);
  const mergedLastSeen = liveReading?.time ?? latest?.last_seen ?? null;

  const triggered = alerts.filter((a) => a.triggered);
  const totalAnomalies = Object.values(anomalies).reduce((sum, list) => sum + list.length, 0);

  async function rotateKey() {
    if (!token) return;
    setRotatedKey(await api.regenerateKey(token, deviceId));
    setDevice(await api.getDevice(token, deviceId));
  }

  async function deleteDevice() {
    if (!token) return;
    if (!confirm("Delete this device and all its telemetry? This cannot be undone.")) return;
    await api.deleteDevice(token, deviceId);
    router.push("/dashboard");
  }

  if (notFound) {
    return (
      <div className="text-center">
        <p className="text-slate-300">Device not found.</p>
        <Link href="/dashboard" className="text-sm text-emerald-400 hover:underline">
          ← Back to devices
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard" className="text-sm text-slate-500 hover:text-slate-300">
          ← Devices
        </Link>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{device?.name ?? "…"}</h1>
            <p className="flex items-center gap-2 text-sm text-slate-400">
              {mergedLastSeen ? `Last reading ${formatRelative(mergedLastSeen)}` : "No data yet"}
              {live && (
                <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                  live
                </span>
              )}
            </p>
          </div>
          <div className="flex gap-1 rounded-lg border border-slate-800 p-1">
            {(Object.keys(RANGES) as RangeKey[]).map((key) => (
              <button
                key={key}
                onClick={() => setRange(key)}
                className={`rounded-md px-3 py-1 text-sm transition ${
                  range === key
                    ? "bg-slate-700 text-slate-100"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {RANGES[key].label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {triggered.length > 0 && (
        <div className="rounded-xl border border-red-900/60 bg-red-950/30 px-4 py-3 text-sm text-red-200">
          <span className="font-medium">
            {triggered.length} alert{triggered.length > 1 ? "s" : ""} triggered:
          </span>{" "}
          {triggered
            .map((a) => `${sensorMeta(a.sensor_name).label} ${a.comparator} ${a.threshold}`)
            .join(", ")}
        </div>
      )}

      {liveValues.size > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {orderSensors([...liveValues.keys()]).map((name) => (
            <div key={name} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
              <div className="text-xs text-slate-500">{sensorMeta(name).label}</div>
              <div className="mt-1 text-lg font-semibold text-slate-100">
                {formatValue(name, liveValues.get(name)!)}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-300">Sensors</h2>
        {totalAnomalies > 0 && (
          <span className="text-xs text-slate-500">
            <span className="text-rose-400">⚠ {totalAnomalies}</span> anomal
            {totalAnomalies === 1 ? "y" : "ies"} in range — dashed red lines mark readings
            beyond {ANOMALY_Z}σ (rolling z-score)
          </span>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {sensorNames.map((name) => (
          <SensorChart
            key={name}
            sensorName={name}
            points={series[name] ?? []}
            anomalies={anomalies[name] ?? []}
            domain={domain}
          />
        ))}
        {sensorNames.length === 0 && (
          <p className="text-sm text-slate-500">
            No telemetry in this range yet. Send a reading with this device&apos;s API key.
          </p>
        )}
      </div>

      <AlertsPanel deviceId={deviceId} sensors={sensorNames} />

      <div className="rounded-2xl border border-slate-800 bg-slate-900/30 p-5">
        <h2 className="text-sm font-medium text-slate-300">Device settings</h2>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            onClick={rotateKey}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm transition hover:border-slate-500"
          >
            Regenerate API key
          </button>
          <button
            onClick={deleteDevice}
            className="rounded-lg border border-red-900/60 px-3 py-1.5 text-sm text-red-300 transition hover:bg-red-950/40"
          >
            Delete device
          </button>
          {device && (
            <span className="text-xs text-slate-600">key: {device.api_key_prefix}…</span>
          )}
        </div>
      </div>

      {rotatedKey && (
        <ApiKeyDialog
          apiKey={rotatedKey.api_key}
          deviceName={rotatedKey.name}
          onClose={() => setRotatedKey(null)}
        />
      )}
    </div>
  );
}
