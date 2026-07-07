"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, Clock3, Download, FileText, Folder, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import { api } from "../../lib/api";

export function RunDetail({ runId }: { runId: string }) {
  const runQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
  });
  const artifactsQuery = useQuery({
    queryKey: ["run-artifacts", runId],
    queryFn: () => api.getRunArtifacts(runId),
  });
  const traceQuery = useQuery({
    queryKey: ["run-trace", runId],
    queryFn: () => api.getRunTrace(runId),
  });
  const run = runQuery.data;
  const artifactFiles = artifactsQuery.data?.files ?? [];
  const hasJsonReport = artifactFiles.includes("report.json");
  const hasHtmlReport = artifactFiles.includes("report.html");
  const hasBrowserUseLog = artifactFiles.includes("browser-use.log");
  const browserUseLogs =
    traceQuery.data?.items
      .filter((event) => event.payload.kind === "browser_use_log")
      .map((event) => ({
        id: event.event_id,
        ts: event.ts,
        level: stringPayload(event.payload, "level") ?? "INFO",
        logger: stringPayload(event.payload, "logger") ?? "browser_use",
        text: stringPayload(event.payload, "text") ?? event.message ?? "",
      })) ?? [];

  if (runQuery.isLoading) {
    return (
      <section className="sp-card p-6 text-sm text-slate-400">
        加载执行结果中
      </section>
    );
  }

  if (runQuery.isError || !run) {
    return (
      <section className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-fail shadow-card">
        执行记录不可用
      </section>
    );
  }

  return (
    <div className="space-y-5">
      <section className="sp-card sp-rise sp-d1 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="sp-kicker">{run.run_id}</p>
            <h2 className="mt-2 font-display text-xl font-semibold">
              执行结果详情
            </h2>
            <p className="mt-2 font-mono text-xs text-slate-500">
              场景：{run.scenario_ids.join(", ")}
            </p>
          </div>
          <StatusBadge value={run.status} />
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-4">
          <Metric label="判定" value={run.verdict ?? "--"} icon={<ShieldAlert size={17} />} />
          <Metric label="耗时" value={formatDuration(run.duration_ms)} icon={<Clock3 size={17} />} />
          <Metric label="失败主因" value={run.failure_primary ?? "--"} icon={<ShieldAlert size={17} />} />
          <Metric label="报告" value={run.report_id ?? "--"} icon={<FileText size={17} />} />
        </div>
      </section>

      <section className="sp-card sp-rise sp-d2 p-5">
        <h3 className="text-sm font-semibold">Artifact 目录</h3>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-slate-50/70 px-3 py-2.5 text-sm">
          <div className="flex min-w-0 items-center gap-2 font-mono text-xs text-slate-600">
            <Folder size={16} className="shrink-0 text-brand" />
            <span className="truncate">{run.artifact_dir}</span>
          </div>
          <div className="flex items-center gap-2">
            <ReportLink
              enabled={hasJsonReport}
              href={api.runReportUrl(run.run_id, "json")}
              label="导出 JSON"
            />
            <ReportLink
              enabled={hasHtmlReport}
              href={api.runReportUrl(run.run_id, "html")}
              label="导出 HTML"
            />
            <ArtifactLink
              enabled={hasBrowserUseLog}
              href={`/api/runs/${run.run_id}/artifacts/browser-use.log`}
              label="查看 Agent 日志"
            />
          </div>
        </div>
        {!hasJsonReport && !hasHtmlReport ? (
          <p className="mt-2 text-xs text-slate-400">
            当前 run 尚未生成 report.json 或 report.html。
          </p>
        ) : null}
      </section>

      <section className="sp-card sp-rise sp-d3 p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Bot size={17} className="text-brand" />
            <h3 className="text-sm font-semibold">browser-use 控制台日志</h3>
          </div>
          <span className="sp-chip border-line bg-slate-50 font-mono text-slate-500">
            {browserUseLogs.length} logs
          </span>
        </div>
        {browserUseLogs.length === 0 ? (
          <div className="sp-empty">当前 run 没有捕获到 browser-use 日志。</div>
        ) : (
          <div className="sp-panel-dark max-h-[420px] overflow-auto p-3 font-mono text-xs">
            {browserUseLogs.map((log) => (
              <div key={log.id} className="border-b border-white/10 py-2 last:border-0">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-slate-400">
                  <span>{formatTime(log.ts)}</span>
                  <span className="rounded-full bg-white/10 px-2 py-0.5">{log.level}</span>
                  <span>{log.logger}</span>
                </div>
                <p className="whitespace-pre-wrap break-words leading-5 text-slate-200">
                  {log.text}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="sp-card sp-rise sp-d4 p-5">
          <h3 className="mb-3 text-sm font-semibold">失败分类</h3>
          <pre className="max-h-[360px] overflow-auto rounded-xl bg-night p-4 font-mono text-xs leading-5 text-slate-100">
            {JSON.stringify(
              {
                primary: run.failure_primary,
                secondary: run.failure_secondary,
                classification: run.failure_classification ?? null,
              },
              null,
              2,
            )}
          </pre>
        </section>
        <section className="sp-card sp-rise sp-d5 p-5">
          <h3 className="mb-3 text-sm font-semibold">Run JSON</h3>
          <pre className="max-h-[360px] overflow-auto rounded-xl bg-night p-4 font-mono text-xs leading-5 text-slate-100">
            {JSON.stringify(run, null, 2)}
          </pre>
        </section>
      </div>
    </div>
  );
}

function ArtifactLink({
  enabled,
  href,
  label,
}: {
  enabled: boolean;
  href: string;
  label: string;
}) {
  if (!enabled) {
    return (
      <span className="inline-flex h-8 items-center gap-1 rounded-lg border border-line px-3 text-xs text-slate-400">
        <FileText size={14} />
        {label}
      </span>
    );
  }
  return (
    <a
      className="inline-flex h-8 items-center gap-1 rounded-lg border border-line bg-white px-3 text-xs font-semibold text-ink transition-all duration-200 hover:-translate-y-px hover:border-slate-300 hover:shadow-card"
      href={href}
      rel="noreferrer"
      target="_blank"
    >
      <FileText size={14} />
      {label}
    </a>
  );
}

function ReportLink({
  enabled,
  href,
  label,
}: {
  enabled: boolean;
  href: string;
  label: string;
}) {
  if (!enabled) {
    return (
      <span className="inline-flex h-8 items-center gap-1 rounded-lg border border-line px-3 text-xs text-slate-400">
        <Download size={14} />
        {label}
      </span>
    );
  }
  return (
    <a
      className="inline-flex h-8 items-center gap-1 rounded-lg border border-line bg-white px-3 text-xs font-semibold text-ink transition-all duration-200 hover:-translate-y-px hover:border-slate-300 hover:shadow-card"
      href={href}
      rel="noreferrer"
      target="_blank"
    >
      <Download size={14} />
      {label}
    </a>
  );
}

function Metric({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-line bg-slate-50/70 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">{label}</p>
        <span className="text-brand">{icon}</span>
      </div>
      <p className="sp-num mt-2 truncate text-lg font-semibold">{value}</p>
    </div>
  );
}

function StatusBadge({ value }: { value: string }) {
  const classes =
    value === "pass"
      ? "border-emerald-200 bg-emerald-50 text-pass"
      : value === "fail" || value === "error"
        ? "border-red-200 bg-red-50 text-fail"
        : value === "running"
          ? "border-blue-200 bg-blue-50 text-run"
          : value === "needs_review"
            ? "border-amber-200 bg-amber-50 text-warn"
            : "border-slate-200 bg-slate-50 text-slate-500";
  return (
    <span className={`sp-chip px-3 py-1.5 text-sm ${classes}`}>
      <span className={`sp-chip-dot ${value === "running" ? "sp-pulse" : ""}`} />
      {value}
    </span>
  );
}

function formatDuration(value: number | null) {
  if (value === null) {
    return "--";
  }
  if (value < 1000) {
    return `${Math.round(value)}ms`;
  }
  return `${Math.round(value / 1000)}s`;
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

function stringPayload(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  return typeof value === "string" ? value : null;
}
