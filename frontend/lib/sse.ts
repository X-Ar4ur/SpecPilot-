"use client";

import { fetchEventSource } from "@microsoft/fetch-event-source";

import type { TraceEvent } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export function subscribeToRunEvents({
  runId,
  signal,
  onEvent,
  onError,
}: {
  runId: string;
  signal: AbortSignal;
  onEvent: (event: TraceEvent) => void;
  onError: (error: unknown) => void;
}) {
  return fetchEventSource(`${API_BASE_URL}/api/runs/${runId}/events`, {
    signal,
    openWhenHidden: true,
    onmessage(message) {
      if (!message.data) {
        return;
      }
      try {
        onEvent(JSON.parse(message.data) as TraceEvent);
      } catch (error) {
        onError(error);
      }
    },
    onerror(error) {
      onError(error);
      throw error;
    },
  });
}
