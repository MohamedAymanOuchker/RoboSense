"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatClock, sensorMeta } from "@/lib/format";
import type { AnomalyPoint } from "@/lib/types";

export interface SeriesPoint {
  time: string;
  value: number;
}

export function SensorChart({
  sensorName,
  points,
  anomalies = [],
  domain,
}: {
  sensorName: string;
  points: SeriesPoint[];
  anomalies?: AnomalyPoint[];
  domain?: [number, number];
}) {
  const meta = sensorMeta(sensorName);
  const data = points.map((p) => ({ t: Date.parse(p.time), value: p.value }));

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-200">{meta.label}</h3>
        <div className="flex items-center gap-2">
          {anomalies.length > 0 && (
            <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-xs font-medium text-rose-300">
              ⚠ {anomalies.length} anomal{anomalies.length === 1 ? "y" : "ies"}
            </span>
          )}
          <span className="text-xs text-slate-500">{meta.unit || "—"}</span>
        </div>
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={domain ?? ["dataMin", "dataMax"]}
              tickFormatter={(ms) => formatClock(new Date(ms as number).toISOString())}
              stroke="#475569"
              fontSize={11}
              minTickGap={48}
              tickLine={false}
            />
            <YAxis
              stroke="#475569"
              fontSize={11}
              width={48}
              domain={["auto", "auto"]}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "#94a3b8" }}
              labelFormatter={(ms) => new Date(ms as number).toLocaleString()}
              formatter={(value) => [`${value} ${meta.unit}`.trim(), meta.label]}
            />
            {anomalies.map((a) => (
              <ReferenceLine
                key={a.time}
                x={Date.parse(a.time)}
                stroke="#f43f5e"
                strokeDasharray="3 3"
                strokeOpacity={0.8}
              />
            ))}
            <Line
              type="monotone"
              dataKey="value"
              stroke={meta.color}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
