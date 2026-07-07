"use client";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleDot,
  Eye,
  MonitorPlay,
  Wrench,
} from "lucide-react";

import type { TraceEvent } from "../../lib/types";

const eventMeta = {
  node_status: { label: "节点", icon: CircleDot },
  browser_step: { label: "动作", icon: Bot },
  browser_frame: { label: "画面", icon: MonitorPlay },
  verification: { label: "验证", icon: CheckCircle2 },
  classification: { label: "分类", icon: Eye },
  repair: { label: "修补", icon: Wrench },
  report: { label: "报告", icon: CheckCircle2 },
  error: { label: "错误", icon: AlertTriangle },
};

export function EventStream({ events }: { events: TraceEvent[] }) {
  const visibleEvents = [...events].reverse();
  return (
    <section className="sp-card sp-rise sp-d3 flex min-h-[360px] flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold">实时事件流</h3>
        <span className="sp-chip border-line bg-slate-50 font-mono text-slate-500">
          {events.length} events
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {visibleEvents.length === 0 ? (
          <div className="grid h-48 place-items-center text-sm text-slate-400">
            等待 SSE 事件
          </div>
        ) : (
          <div className="space-y-2">
            {visibleEvents.map((event) => (
              <EventItem key={event.event_id} event={event} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function EventItem({ event }: { event: TraceEvent }) {
  const meta = eventMeta[event.type];
  const Icon = meta.icon;
  const browserUseLog = browserUseLogPayload(event);
  if (browserUseLog) {
    return <BrowserUseLogItem event={event} log={browserUseLog} />;
  }
  return (
    <article className="rounded-xl border border-line bg-slate-50/70 px-3 py-2 text-sm transition-colors hover:bg-slate-50">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-white text-brand shadow-[0_1px_2px_rgba(16,26,46,0.06)]">
            <Icon size={14} />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{meta.label}</span>
              {event.node ? (
                <span className="rounded-full bg-white px-2 py-0.5 font-mono text-xs text-slate-500">
                  {event.node}
                </span>
              ) : null}
              {event.status ? <StatusPill value={event.status} /> : null}
            </div>
            <p className="mt-1 break-words text-slate-600">
              {event.message ?? summarizePayload(event.payload)}
            </p>
          </div>
        </div>
        <time className="shrink-0 font-mono text-xs text-slate-400">
          {formatTime(event.ts)}
        </time>
      </div>
      {Object.keys(event.payload).length > 0 ? (
        <pre className="mt-2 max-h-32 overflow-auto rounded-lg bg-night p-2 font-mono text-[11px] leading-4 text-slate-100">
          {JSON.stringify(event.payload, null, 2)}
        </pre>
      ) : null}
    </article>
  );
}

function BrowserUseLogItem({
  event,
  log,
}: {
  event: TraceEvent;
  log: { level: string; logger: string; text: string };
}) {
  return (
    <article className="rounded-xl border border-white/10 bg-night px-3 py-2 font-mono text-xs text-slate-100">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-blue-200">
              browser-use
            </span>
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-slate-300">
              {log.level}
            </span>
            <span className="truncate text-slate-400">{log.logger}</span>
          </div>
          <p className="whitespace-pre-wrap break-words leading-5">{log.text}</p>
        </div>
        <time className="shrink-0 text-slate-500">{formatTime(event.ts)}</time>
      </div>
    </article>
  );
}

function StatusPill({ value }: { value: string }) {
  const classes =
    value === "pass" || value === "success"
      ? "bg-emerald-50 text-pass"
      : value === "fail" || value === "failed" || value === "error"
        ? "bg-red-50 text-fail"
        : value === "running"
          ? "bg-blue-50 text-run"
          : value === "needs_review" || value === "retrying"
            ? "bg-amber-50 text-warn"
            : "bg-white text-slate-500";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs ${classes}`}>{value}</span>
  );
}

function summarizePayload(payload: Record<string, unknown>) {
  const preferred = ["action", "summary", "reason", "url", "step"];
  for (const key of preferred) {
    const value = payload[key];
    if (typeof value === "string" || typeof value === "number") {
      return `${key}: ${value}`;
    }
  }
  return "收到 TraceEvent";
}

function browserUseLogPayload(event: TraceEvent) {
  if (event.payload.kind !== "browser_use_log") {
    return null;
  }
  const text = event.payload.text;
  const level = event.payload.level;
  const logger = event.payload.logger;
  if (typeof text !== "string") {
    return null;
  }
  return {
    text,
    level: typeof level === "string" ? level : "INFO",
    logger: typeof logger === "string" ? logger : "browser_use",
  };
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}
