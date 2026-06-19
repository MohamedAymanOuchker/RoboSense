"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiKeyDialog } from "@/components/ApiKeyDialog";
import { DeviceCard } from "@/components/DeviceCard";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Device, DeviceWithKey } from "@/lib/types";

export default function DashboardPage() {
  const { token } = useAuth();
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<DeviceWithKey | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    setDevices(await api.listDevices(token));
  }, [token]);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  async function createDevice(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createDevice(token, name.trim());
      setName("");
      setNewKey(created);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create device");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Devices</h1>
          <p className="text-sm text-slate-400">
            {devices ? `${devices.length} device${devices.length === 1 ? "" : "s"}` : "Loading…"}
          </p>
        </div>
        <form onSubmit={createDevice} className="flex items-center gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New device name"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-emerald-500"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-slate-950 transition hover:bg-emerald-400 disabled:opacity-50"
          >
            Add device
          </button>
        </form>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {devices && devices.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-800 p-10 text-center">
          <p className="text-slate-300">No devices yet.</p>
          <p className="mt-1 text-sm text-slate-500">
            Add one above, or run <code className="text-slate-300">make seed</code> to create a
            demo device with sample telemetry.
          </p>
        </div>
      )}

      {devices && devices.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {devices.map((device) => (
            <DeviceCard key={device.id} device={device} />
          ))}
        </div>
      )}

      {newKey && (
        <ApiKeyDialog
          apiKey={newKey.api_key}
          deviceName={newKey.name}
          onClose={() => setNewKey(null)}
        />
      )}
    </div>
  );
}
