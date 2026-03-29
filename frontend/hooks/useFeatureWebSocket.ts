"use client";

import { useEffect, useRef, useState } from "react";

export interface FeatureEvent {
  type: string;
  feature_id: string;
  stage?: string;
  message?: string;
  data?: Record<string, unknown>;
  timestamp?: string;
}

export function useFeatureWebSocket(featureId: string) {
  const [events, setEvents] = useState<FeatureEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"}/ws/features/${featureId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data as string) as FeatureEvent;
        setEvents((prev) => [...prev, event]);
      } catch {
        // ignore malformed messages
      }
    };

    return () => {
      ws.close();
    };
  }, [featureId]);

  return { events, connected };
}
