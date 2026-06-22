"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatRelative, formatValue, sensorMeta } from "@/lib/format";
import type { AlertStatus, Device, LatestSnapshot } from "@/lib/types";
import { useDeviceStream } from "@/lib/useDeviceStream";

const PREVIEW_SENSORS = ["battery", "temperature", "speed", "rssi"];

export function DeviceCard({ device }: { device: Device }) {
  const { token } = useAuth();
  const [latest, setLatest] = useState<LatestSnapshot | null>(null);
  const [alerts, setAlerts] = useState<AlertStatus[]>([]);
  const { reading } = useDeviceStream(device.id);

  useEffect(() => {
    if (!token) return;
    let active = true;
    // Initial snapshot once; live values then arrive via SSE.
    api
      .latest(token, device.id)
      .then((l) => active && setLatest(l))
      .catch(() => {});
    // Alert status still polls (it's a server-side evaluation), but slowly.
    const loadAlerts = () =>
      api
        .alertStatus(token, device.id)
        .then((a) => active && setAlerts(a))
        .catch(() => {});
    loadAlerts();
    const interval = setInterval(loadAlerts, 10000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [token, device.id]);

  // Latest snapshot values, with any live-streamed reading layered on top.
  const values = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of latest?.readings ?? []) map.set(r.sensor_name, r.value);
    if (reading) for (const [k, v] of Object.entries(reading.readings)) map.set(k, v);
    return map;
  }, [latest, reading]);

  const lastSeen = reading?.time ?? latest?.last_seen ?? null;
  const triggered = alerts.filter((a) => a.triggered);
  const preview = PREVIEW_SENSORS.filter((s) => values.has(s)).slice(0, 4);

  return (
    <Link
      href={`/dashboard/devices/${device.id}`}
      className="group flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/50 p-5 transition hover:border-slate-600 hover:bg-slate-900"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-medium text-slate-100">{device.name}</h3>
          <p className="text-xs text-slate-500">
            {lastSeen ? `Updated ${formatRelative(lastSeen)}` : "No data yet"}
          </p>
        </div>
        {triggered.length > 0 ? (
          <span className="rounded-full bg-red-500/15 px-2.5 py-1 text-xs font-medium text-red-300">
            {triggered.length} alert{triggered.length > 1 ? "s" : ""}
          </span>
        ) : (
          <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300">
            OK
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        {preview.length === 0 && (
          <p className="col-span-2 text-sm text-slate-500">Waiting for telemetry…</p>
        )}
        {preview.map((name) => (
          <div key={name} className="rounded-lg bg-slate-950/60 px-3 py-2">
            <div className="text-xs text-slate-500">{sensorMeta(name).label}</div>
            <div className="text-sm font-medium text-slate-200">
              {formatValue(name, values.get(name)!)}
            </div>
          </div>
        ))}
      </div>

      <div className="text-xs text-slate-600 group-hover:text-slate-500">
        {device.api_key_prefix}… · view details →
      </div>
    </Link>
  );
}
