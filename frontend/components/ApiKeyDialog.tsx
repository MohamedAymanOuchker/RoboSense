"use client";

import { useState } from "react";

export function ApiKeyDialog({
  apiKey,
  deviceName,
  onClose,
}: {
  apiKey: string;
  deviceName: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard may be unavailable (e.g. non-secure context); ignore
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <h2 className="text-lg font-medium">API key for “{deviceName}”</h2>
        <p className="mt-1 text-sm text-slate-400">
          Copy this now — it is shown only once. Use it as the{" "}
          <code className="text-slate-300">X-API-Key</code> header when ingesting telemetry.
        </p>
        <div className="mt-4 flex items-center gap-2">
          <code className="flex-1 overflow-x-auto rounded-lg bg-slate-950 px-3 py-2 text-sm text-emerald-300">
            {apiKey}
          </code>
          <button
            onClick={copy}
            className="shrink-0 rounded-lg border border-slate-700 px-3 py-2 text-sm transition hover:border-slate-500"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <button
          onClick={onClose}
          className="mt-5 w-full rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-slate-950 transition hover:bg-emerald-400"
        >
          Done
        </button>
      </div>
    </div>
  );
}
