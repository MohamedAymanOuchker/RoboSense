"use client";

import { useEffect, useRef, useState } from "react";

import { useAuth } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface StreamReading {
  time: string;
  readings: Record<string, number>;
}

/**
 * Subscribe to a device's live telemetry via Server-Sent Events. Returns the
 * most recent pushed reading and whether the stream is currently connected.
 * EventSource can't set headers, so the JWT is passed as a query parameter.
 */
export function useDeviceStream(deviceId: number): {
  reading: StreamReading | null;
  connected: boolean;
} {
  const { token } = useAuth();
  const [reading, setReading] = useState<StreamReading | null>(null);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!token) return;
    const url = `${API_URL}/api/devices/${deviceId}/stream?token=${encodeURIComponent(token)}`;
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setConnected(true);
    source.addEventListener("reading", (event) => {
      try {
        setReading(JSON.parse((event as MessageEvent).data) as StreamReading);
      } catch {
        // ignore malformed event
      }
    });
    source.onerror = () => setConnected(false);

    return () => {
      source.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [token, deviceId]);

  return { reading, connected };
}
