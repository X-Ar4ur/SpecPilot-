"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock3, FileJson, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { api } from "../../lib/api";
import type { Run } from "../../lib/types";

const runHistoryColumns =
  "minmax(300px,1.6fr) minmax(150px,0.8fr) 92px 104px minmax(132px,0.8fr) minmax(240px,1.1fr) 88px";

export function RunHistory() {
  const [query, setQuery] = useState("");
  const runsQuery = useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
  const filtered = useMemo(
    () => {
      const runs = runsQuery.data?.items ?? [];
      return runs.filter((run) => {
        const text = [
          run.run_id,
          run.status,
          run.verdict ?? "",
          run.failure_primary ?? "",
          ...run.scenario_ids,
        ].join(" ");
        return text.includes(query);
      });
    },
    [query, runsQuery.data?.items],
  );

  return (
    <div className="space-y-4">
      <div className="sp-rise sp-d1 relative max-w-xl">
        <Search className="absolute left-3 top-3 text-slate-400" size={16} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索 run、状态、场景或失败类型"
          className="sp-input w-full pl-9"
        />
      </div>
      <section className="sp-card sp-rise sp-d2 overflow-hidden">
        <div className="overflow-x-auto">
          <div className="min-w-[1120px]">
            <div
              className="grid items-center gap-4 border-b border-line bg-slate-50/80 px-4 py-3"
              style={{ gridTemplateColumns: runHistoryColumns }}
            >
              <span className="sp-th">Run</span>
              <span className="sp-th">场景</span>
              <span className="sp-th text-center">状态</span>
              <span className="sp-th">耗时</span>
              <span className="sp-th">失败主因</span>
              <span className="sp-th">报告</span>
              <span className="sp-th text-right">详情</span>
            </div>
            {runsQuery.isError ? (
              <EmptyRow text="执行记录接口暂不可用" />
            ) : filtered.length === 0 ? (
              <EmptyRow text="暂无执行记录" />
            ) : (
              <div className="divide-y divide-line">
                {filtered.map((run) => (
                  <RunRow key={run.run_id} run={run} />
                ))}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function RunRow({ run }: { run: Run }) {
  return (
    <div
      className="grid items-center gap-4 px-4 py-3 text-sm transition-colors hover:bg-slate-50/70"
      style={{ gridTemplateColumns: runHistoryColumns }}
    >
      <div className="min-w-0">
        <Link
          href={`/runs/${run.run_id}`}
          title={run.run_id}
          className="block truncate font-mono text-[13px] font-semibold text-ink transition-colors hover:text-run"
        >
          {run.run_id}
        </Link>
        <p className="mt-1 text-xs text-slate-400">
          {formatDate(run.started_at)}
        </p>
      </div>
      <span
        className="min-w-0 truncate font-mono text-xs text-slate-500"
        title={run.scenario_ids.join(", ")}
      >
        {run.scenario_ids.join(", ")}
      </span>
      <div className="flex justify-center">
        <StatusBadge value={run.status} />
      </div>
      <span className="flex items-center gap-1 font-mono text-xs text-slate-500 tabular-nums">
        <Clock3 size={14} />
        {formatDuration(run.duration_ms)}
      </span>
      <span className="min-w-0 truncate text-slate-600" title={run.failure_primary ?? "--"}>
        {run.failure_primary ?? "--"}
      </span>
      <span
        className="flex min-w-0 items-center gap-1 font-mono text-xs text-slate-500"
        title={run.report_id ?? "--"}
      >
        <FileJson size={14} className="shrink-0" />
        <span className="truncate">{run.report_id ?? "--"}</span>
      </span>
      <div className="text-right">
        <Link
          href={`/runs/${run.run_id}`}
          className="inline-flex items-center rounded-lg border border-line bg-white px-3 py-1.5 text-xs font-medium transition-all duration-200 hover:-translate-y-px hover:border-slate-300 hover:shadow-card"
        >
          打开
        </Link>
      </div>
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
    <span className={`sp-chip ${classes}`}>
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

function formatDate(value: string | null) {
  if (!value) {
    return "未开始";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function EmptyRow({ text }: { text: string }) {
  return (
    <div className="px-4 py-10 text-center text-sm text-slate-400">{text}</div>
  );
}
