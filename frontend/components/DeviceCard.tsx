"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatRelative, formatValue, sensorMeta } from "@/lib/format";
import type { AlertStatus, Device, LatestSnapshot } from "@/lib/types";

const PREVIEW_SENSORS = ["battery", "temperature", "speed", "rssi"];

export function DeviceCard({ device }: { device: Device }) {
  const { token } = useAuth();
  const [latest, setLatest] = useState<LatestSnapshot | null>(null);
  const [alerts, setAlerts] = useState<AlertStatus[]>([]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    const load = () => {
      Promise.all([api.latest(token, device.id), api.alertStatus(token, device.id)])
        .then(([l, a]) => {
          if (active) {
            setLatest(l);
            setAlerts(a);
          }
        })
        .catch(() => {});
    };
    load();
    const interval = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [token, device.id]);

  const triggered = alerts.filter((a) => a.triggered);
  const byName = new Map(latest?.readings.map((r) => [r.sensor_name, r]) ?? []);
  const preview = PREVIEW_SENSORS.filter((s) => byName.has(s)).slice(0, 4);

  return (
    <Link
      href={`/dashboard/devices/${device.id}`}
      className="group flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/50 p-5 transition hover:border-slate-600 hover:bg-slate-900"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-medium text-slate-100">{device.name}</h3>
          <p className="text-xs text-slate-500">
            {latest?.last_seen ? `Updated ${formatRelative(latest.last_seen)}` : "No data yet"}
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
        {preview.map((name) => {
          const reading = byName.get(name)!;
          return (
            <div key={name} className="rounded-lg bg-slate-950/60 px-3 py-2">
              <div className="text-xs text-slate-500">{sensorMeta(name).label}</div>
              <div className="text-sm font-medium text-slate-200">
                {formatValue(name, reading.value)}
              </div>
            </div>
          );
        })}
      </div>

      <div className="text-xs text-slate-600 group-hover:text-slate-500">
        {device.api_key_prefix}… · view details →
      </div>
    </Link>
  );
}
