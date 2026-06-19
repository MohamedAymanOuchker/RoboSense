"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatClock, sensorMeta } from "@/lib/format";

export interface SeriesPoint {
  time: string;
  value: number;
}

export function SensorChart({
  sensorName,
  points,
}: {
  sensorName: string;
  points: SeriesPoint[];
}) {
  const meta = sensorMeta(sensorName);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-200">{meta.label}</h3>
        <span className="text-xs text-slate-500">{meta.unit || "—"}</span>
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" vertical={false} />
            <XAxis
              dataKey="time"
              tickFormatter={formatClock}
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
              labelFormatter={(value) => new Date(value as string).toLocaleString()}
              formatter={(value) => [`${value} ${meta.unit}`.trim(), meta.label]}
            />
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
