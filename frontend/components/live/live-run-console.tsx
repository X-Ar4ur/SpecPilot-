"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, Radio, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import { subscribeToRunEvents } from "../../lib/sse";
import type { BoundingBox, BrowserFrame, TraceEvent } from "../../lib/types";
import { AgentFlow } from "./agent-flow";
import { BrowserFrameView } from "./browser-frame";
import { EventStream } from "./event-stream";
import { FrameTimeline } from "./frame-timeline";

export function LiveRunConsole({ runId }: { runId: string }) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [sseError, setSseError] = useState<string | null>(null);
  const [selectedFrameId, setSelectedFrameId] = useState<string | null>(null);
  const runQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: 5000,
  });
  const runStatus = runQuery.data?.status;
  const traceComplete = useMemo(
    () => hasTerminalTraceEvent(events, runStatus),
    [events, runStatus],
  );
  const artifactsQuery = useQuery({
    queryKey: ["run-artifacts", runId],
    queryFn: () => api.getRunArtifacts(runId),
    refetchInterval: 5000,
  });
  const { data: traceData, refetch: refetchTrace } = useQuery({
    queryKey: ["run-trace", runId],
    queryFn: () => api.getRunTrace(runId),
    refetchInterval:
      runStatus === undefined ||
      runStatus === "queued" ||
      runStatus === "running" ||
      !traceComplete
        ? 3000
        : false,
  });

  useEffect(() => {
    const controller = new AbortController();
    setSseError(null);
    setEvents([]);
    void subscribeToRunEvents({
      runId,
      signal: controller.signal,
      onEvent(event) {
        setEvents((current) => {
          if (current.some((item) => item.event_id === event.event_id)) {
            return current;
          }
          return [...current, event].slice(-300);
        });
      },
      onError(error) {
        if (!controller.signal.aborted) {
          setSseError(error instanceof Error ? error.message : "SSE 连接异常");
        }
      },
    });
    return () => controller.abort();
  }, [runId]);

  useEffect(() => {
    const traceEvents = traceData?.items ?? [];
    if (traceEvents.length === 0) {
      return;
    }
    setEvents((current) => mergeEvents(current, traceEvents));
  }, [traceData?.items]);

  useEffect(() => {
    if (isTerminalRunStatus(runStatus) && !traceComplete) {
      void refetchTrace();
    }
  }, [runStatus, traceComplete, refetchTrace]);

  const eventFrames = useMemo(
    () =>
      events
        .filter((event) => event.type === "browser_frame")
        .map((event) => frameFromEvent(runId, event))
        .filter((frame): frame is BrowserFrame => frame !== null),
    [events, runId],
  );
  const artifactFrames = useMemo(
    () =>
      (artifactsQuery.data?.files ?? [])
        .filter((file) => isImageArtifact(file))
        .map((file, index) => frameFromArtifact(runId, file, index)),
    [artifactsQuery.data?.files, runId],
  );
  const frames = useMemo(() => {
    const seen = new Set<string>();
    return [...eventFrames, ...artifactFrames].filter((frame) => {
      const key = frame.artifactPath ?? frame.eventId;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }, [artifactFrames, eventFrames]);
  const selectedFrame =
    frames.find((frame) => frame.eventId === selectedFrameId) ??
    eventFrames.at(-1) ??
    frames.at(-1) ??
    null;
  const latestStep = [...events]
    .reverse()
    .find((event) => event.type === "browser_step" && event.payload.kind !== "browser_use_log");
  const latestBrowserUseLog = [...events]
    .reverse()
    .find((event) => event.type === "browser_step" && event.payload.kind === "browser_use_log");
  const latestVerification = [...events]
    .reverse()
    .find((event) => event.type === "verification");
  const latestClassification = [...events]
    .reverse()
    .find((event) => event.type === "classification");
  const finalVerdict =
    runQuery.data?.verdict ??
    stringPayload(latestVerification, "verdict") ??
    runQuery.data?.status ??
    "running";

  return (
    <div className="space-y-5">
      <section className="sp-card sp-rise p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="sp-kicker">Live Run</p>
            <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight">
              {runId}
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              SSE TraceEvent、LangGraph 节点、browser_frame 和 artifact 截图时间线。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge value={runQuery.data?.status ?? "connecting"} />
            <StatusBadge value={`verdict: ${finalVerdict}`} />
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <SummaryMetric label="SSE 事件" value={String(events.length)} />
          <SummaryMetric label="浏览器帧" value={String(frames.length)} />
          <SummaryMetric
            label="最新步骤"
            value={
              latestStep?.message ??
              stringPayload(latestStep, "action") ??
              stringPayload(latestBrowserUseLog, "text") ??
              latestBrowserUseLog?.message ??
              "--"
            }
          />
          <SummaryMetric
            label="失败分类"
            value={
              runQuery.data?.failure_primary ??
              stringPayload(latestClassification, "primary") ??
              "--"
            }
          />
        </div>
        {sseError ? (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-warn">
            <AlertTriangle size={16} />
            SSE 暂不可用：{sseError}
          </div>
        ) : (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-pass">
            {events.length === 0 ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Radio size={16} className="sp-pulse" />
            )}
            {events.length === 0 ? "正在等待事件 / trace 回放" : "事件流已接收"}
          </div>
        )}
      </section>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.35fr)_minmax(420px,0.9fr)]">
        <div className="space-y-5">
          <AgentFlow events={events} />
          <EventStream events={events} />
        </div>
        <div className="space-y-5">
          <BrowserFrameView frame={selectedFrame} />
          <FrameTimeline
            frames={frames}
            selectedEventId={selectedFrame?.eventId ?? null}
            onSelect={(frame) => setSelectedFrameId(frame.eventId)}
          />
          <FinalPanel
            verdict={finalVerdict}
            verification={latestVerification}
            classification={latestClassification}
          />
        </div>
      </div>
    </div>
  );
}

function FinalPanel({
  verdict,
  verification,
  classification,
}: {
  verdict: string;
  verification: TraceEvent | undefined;
  classification: TraceEvent | undefined;
}) {
  return (
    <section className="sp-card p-4">
      <div className="mb-3 flex items-center gap-2">
        {verdict === "pass" ? (
          <CheckCircle2 className="text-pass" size={18} />
        ) : (
          <ShieldAlert className="text-warn" size={18} />
        )}
        <h3 className="text-sm font-semibold">最终判定与失败摘要</h3>
      </div>
      <div className="grid gap-3 text-sm">
        <KeyValue label="verdict" value={verdict} />
        <KeyValue
          label="verification"
          value={verification?.message ?? summarizePayload(verification?.payload)}
        />
        <KeyValue
          label="classification"
          value={classification?.message ?? summarizePayload(classification?.payload)}
        />
      </div>
    </section>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-slate-50/70 px-3 py-2.5">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold">{value}</p>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-slate-50/70 px-3 py-2">
      <span className="mr-2 font-mono text-xs text-brand">{label}</span>
      <span>{value || "--"}</span>
    </div>
  );
}

function StatusBadge({ value }: { value: string }) {
  const classes =
    value.includes("pass") || value === "success"
      ? "border-emerald-200 bg-emerald-50 text-pass"
      : value.includes("fail") || value === "error"
        ? "border-red-200 bg-red-50 text-fail"
        : value.includes("review") || value === "retrying"
          ? "border-amber-200 bg-amber-50 text-warn"
          : "border-blue-200 bg-blue-50 text-run";
  return (
    <span className={`sp-chip px-3 py-1.5 text-sm ${classes}`}>
      <span
        className={`sp-chip-dot ${
          value === "running" || value === "connecting" ? "sp-pulse" : ""
        }`}
      />
      {value}
    </span>
  );
}

function frameFromEvent(runId: string, event: TraceEvent): BrowserFrame | null {
  const base64 = firstString(event.payload, [
    "image_base64",
    "screenshot_base64",
    "base64",
  ]);
  const artifactPath = firstString(event.payload, [
    "screenshot_path",
    "artifact_path",
    "path",
  ]);
  const usableArtifactPath = artifactPath && !isAbsolutePath(artifactPath) ? artifactPath : null;
  if (!base64 && !usableArtifactPath) {
    return null;
  }
  return {
    eventId: event.event_id,
    ts: event.ts,
    src: base64
      ? dataUrl(base64)
      : artifactUrl(runId, usableArtifactPath as string),
    artifactPath: usableArtifactPath ?? undefined,
    url: firstString(event.payload, ["url", "current_url"]) ?? undefined,
    step: firstNumber(event.payload, ["step", "step_index", "step_number"]),
    action: firstString(event.payload, ["action", "summary", "message"]) ?? event.message ?? undefined,
    targetBox: extractBox(event.payload),
  };
}

function frameFromArtifact(
  runId: string,
  artifactPath: string,
  index: number,
): BrowserFrame {
  return {
    eventId: `artifact-${artifactPath}`,
    ts: "",
    src: artifactUrl(runId, artifactPath),
    artifactPath,
    step: index + 1,
    action: artifactPath,
  };
}

function extractBox(payload: Record<string, unknown>): BoundingBox | undefined {
  const raw =
    objectPayload(payload, "target_box") ??
    objectPayload(payload, "bounding_box") ??
    objectPayload(payload, "box");
  if (!raw) {
    return undefined;
  }
  const x = numberValue(raw, "x");
  const y = numberValue(raw, "y");
  const width = numberValue(raw, "width") ?? numberValue(raw, "w");
  const height = numberValue(raw, "height") ?? numberValue(raw, "h");
  if (x === undefined || y === undefined || width === undefined || height === undefined) {
    return undefined;
  }
  const viewportWidth = firstNumber(payload, ["viewport_width", "image_width"]);
  const viewportHeight = firstNumber(payload, ["viewport_height", "image_height"]);
  return {
    x: normalizeCoord(x, viewportWidth),
    y: normalizeCoord(y, viewportHeight),
    width: normalizeCoord(width, viewportWidth),
    height: normalizeCoord(height, viewportHeight),
  };
}

function normalizeCoord(value: number, total: number | undefined) {
  if (value <= 1) {
    return clamp(value * 100);
  }
  if (total && total > 0) {
    return clamp((value / total) * 100);
  }
  return clamp(value);
}

function clamp(value: number) {
  return Math.max(0, Math.min(100, value));
}

function artifactUrl(runId: string, artifactPath: string) {
  return `/api/runs/${runId}/artifacts/${artifactPath
    .split("/")
    .map(encodeURIComponent)
    .join("/")}`;
}

function dataUrl(value: string) {
  return value.startsWith("data:") ? value : `data:image/jpeg;base64,${value}`;
}

function isImageArtifact(file: string) {
  return (
    file.startsWith("screenshots/") &&
    /\.(png|jpe?g|webp)$/i.test(file)
  );
}

function mergeEvents(current: TraceEvent[], incoming: TraceEvent[]) {
  const seen = new Set(current.map((event) => event.event_id));
  const merged = [...current];
  for (const event of incoming) {
    if (!seen.has(event.event_id)) {
      seen.add(event.event_id);
      merged.push(event);
    }
  }
  return merged
    .sort((left, right) => Date.parse(left.ts) - Date.parse(right.ts))
    .slice(-300);
}

function isTerminalRunStatus(status: string | undefined) {
  return (
    status === "pass" ||
    status === "fail" ||
    status === "error" ||
    status === "needs_review" ||
    status === "cancelled"
  );
}

function hasTerminalTraceEvent(events: TraceEvent[], runStatus: string | undefined) {
  const hasReport = events.some(
    (event) =>
      event.type === "report" ||
      (event.type === "node_status" && event.node === "Reporter" && event.status === "success"),
  );
  if (hasReport) {
    return true;
  }
  if (!isTerminalRunStatus(runStatus)) {
    return false;
  }
  return events.some(
    (event) =>
      event.status === "failed" ||
      event.status === "fail" ||
      event.status === "error" ||
      event.type === "classification",
  );
}

function isAbsolutePath(path: string) {
  return /^[a-zA-Z]:[\\/]/.test(path) || path.startsWith("\\\\") || path.startsWith("/");
}

function firstString(payload: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return null;
}

function firstNumber(payload: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "number") {
      return value;
    }
  }
  return undefined;
}

function objectPayload(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function numberValue(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  return typeof value === "number" ? value : undefined;
}

function stringPayload(event: TraceEvent | undefined, key: string) {
  const value = event?.payload[key];
  return typeof value === "string" ? value : null;
}

function summarizePayload(payload: Record<string, unknown> | undefined) {
  if (!payload) {
    return "--";
  }
  const preferred = ["primary", "verdict", "reason", "summary", "status"];
  for (const key of preferred) {
    const value = payload[key];
    if (typeof value === "string" || typeof value === "number") {
      return `${key}: ${value}`;
    }
  }
  return Object.keys(payload).length > 0 ? "见事件 payload" : "--";
}
