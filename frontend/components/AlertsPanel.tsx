"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { COMPARATOR_LABEL, formatValue, sensorMeta } from "@/lib/format";
import type { AlertStatus, Comparator } from "@/lib/types";

const COMPARATORS: Comparator[] = ["lt", "lte", "gt", "gte"];

export function AlertsPanel({
  deviceId,
  sensors,
}: {
  deviceId: number;
  sensors: string[];
}) {
  const { token } = useAuth();
  const [statuses, setStatuses] = useState<AlertStatus[]>([]);
  const [sensor, setSensor] = useState("battery");
  const [comparator, setComparator] = useState<Comparator>("lt");
  const [threshold, setThreshold] = useState("20");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!token) return;
    setStatuses(await api.alertStatus(token, deviceId));
  }, [token, deviceId]);

  useEffect(() => {
    refresh().catch(() => {});
    const interval = setInterval(() => refresh().catch(() => {}), 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function addRule(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    try {
      await api.createAlert(token, deviceId, {
        sensor_name: sensor,
        comparator,
        threshold: Number(threshold),
      });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function removeRule(ruleId: number) {
    if (!token) return;
    await api.deleteAlert(token, deviceId, ruleId);
    await refresh();
  }

  const sensorOptions = sensors.length > 0 ? sensors : ["battery", "temperature"];

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5">
      <h2 className="text-sm font-medium text-slate-200">Alert rules</h2>
      <p className="mt-1 text-xs text-slate-500">
        Trigger when a sensor&apos;s latest reading crosses a threshold.
      </p>

      <ul className="mt-4 space-y-2">
        {statuses.length === 0 && (
          <li className="text-sm text-slate-500">No rules yet.</li>
        )}
        {statuses.map((s) => (
          <li
            key={s.rule_id}
            className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
              s.triggered
                ? "border-red-900/60 bg-red-950/30"
                : "border-slate-800 bg-slate-950/40"
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  s.triggered ? "bg-red-400" : "bg-emerald-400"
                }`}
              />
              <span className="text-slate-300">
                {sensorMeta(s.sensor_name).label} {COMPARATOR_LABEL[s.comparator]} {s.threshold}
              </span>
              <span className="text-xs text-slate-500">
                {s.latest_value === null
                  ? "no data"
                  : `now ${formatValue(s.sensor_name, s.latest_value)}`}
              </span>
            </div>
            <button
              onClick={() => removeRule(s.rule_id)}
              className="text-xs text-slate-500 transition hover:text-red-400"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={addRule} className="mt-4 flex flex-wrap items-center gap-2">
        <select
          value={sensor}
          onChange={(e) => setSensor(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm outline-none focus:border-emerald-500"
        >
          {sensorOptions.map((s) => (
            <option key={s} value={s}>
              {sensorMeta(s).label}
            </option>
          ))}
        </select>
        <select
          value={comparator}
          onChange={(e) => setComparator(e.target.value as Comparator)}
          className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm outline-none focus:border-emerald-500"
        >
          {COMPARATORS.map((c) => (
            <option key={c} value={c}>
              {COMPARATOR_LABEL[c]}
            </option>
          ))}
        </select>
        <input
          type="number"
          step="any"
          value={threshold}
          onChange={(e) => setThreshold(e.target.value)}
          className="w-24 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm outline-none focus:border-emerald-500"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm transition hover:border-emerald-500 hover:text-emerald-300 disabled:opacity-50"
        >
          Add rule
        </button>
      </form>
    </div>
  );
}
