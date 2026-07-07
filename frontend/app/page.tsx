"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BookOpenText,
  CheckCircle2,
  Clock3,
  FileText,
  ListChecks,
  Play,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "../lib/api";
import type { Run } from "../lib/types";

const statusColors = {
  pass: "#0B8F5F",
  fail: "#DF3340",
  needs_review: "#B26205",
  running: "#2B5CE6",
  queued: "#64748B",
  error: "#DF3340",
  cancelled: "#64748B",
};

const chartTooltipStyle = {
  borderRadius: 12,
  border: "1px solid #E3E8F1",
  boxShadow: "0 10px 28px -14px rgba(16,26,46,0.25)",
  fontSize: 12,
  padding: "8px 12px",
};

export default function Home() {
  const featuresQuery = useQuery({
    queryKey: ["features"],
    queryFn: api.listFeatures,
  });
  const scenariosQuery = useQuery({
    queryKey: ["scenarios"],
    queryFn: () => api.listScenarios(),
  });
  const runsQuery = useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: api.getSettings,
  });
  const features = featuresQuery.data?.items ?? [];
  const scenarios = scenariosQuery.data?.items ?? [];
  const runs = runsQuery.data?.items ?? [];
  const provider =
    settingsQuery.data?.models.text_llm_provider ?? "openai_compatible";
  const model =
    provider === "openai_compatible"
      ? settingsQuery.data?.models.openai_compatible_model ?? "gpt-5.5"
      : provider === "browser_use"
        ? settingsQuery.data?.models.browser_use_model ?? "bu-latest"
        : settingsQuery.data?.models.deepseek_model ?? "deepseek-v4-pro";
  const passCount = runs.filter((run) => run.verdict === "pass").length;
  const failCount = runs.filter((run) => run.verdict === "fail").length;
  const runningCount = runs.filter((run) => run.status === "running").length;
  const passRate =
    runs.length > 0 ? `${Math.round((passCount / runs.length) * 100)}%` : "--";
  const avgDuration = averageDuration(runs);
  const difficultyData = ["simple", "medium", "hard"].map((difficulty) => ({
    name:
      difficulty === "simple"
        ? "简单"
        : difficulty === "medium"
          ? "中等"
          : "困难",
    value: scenarios.filter((scenario) => scenario.difficulty === difficulty)
      .length,
  }));
  const failureData = summarizeFailures(runs);

  return (
    <div className="space-y-6">
      <header className="sp-rise flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="sp-kicker">Workbench</p>
          <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight">
            工作台
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            手册索引、场景生成、browser-use 执行与验证报告的集中视图。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ActionLink href="/features" icon={<BookOpenText size={16} />}>
            功能点
          </ActionLink>
          <ActionLink href="/scenarios" icon={<ListChecks size={16} />}>
            场景表
          </ActionLink>
          <ActionLink href="/runs" icon={<FileText size={16} />}>
            执行记录
          </ActionLink>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="功能点"
          value={String(features.length)}
          hint="手册证据驱动"
          icon={<BookOpenText size={18} />}
          delay="sp-d1"
        />
        <Metric
          label="测试场景"
          value={String(scenarios.length)}
          hint="自然语言步骤"
          icon={<ListChecks size={18} />}
          delay="sp-d2"
        />
        <Metric
          label="运行中"
          value={String(runningCount)}
          hint="browser-use 本地执行"
          icon={<Activity size={18} />}
          delay="sp-d3"
        />
        <Metric
          label="通过率"
          value={passRate}
          hint={`失败 ${failCount} 次`}
          icon={<ShieldCheck size={18} />}
          delay="sp-d4"
        />
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="sp-card sp-rise sp-d3 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold">场景难度分布</h3>
            <span className="font-mono text-xs text-slate-400">
              {scenarios.length} 条
            </span>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={difficultyData} barSize={56}>
                <defs>
                  <linearGradient id="sp-bar" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2B5CE6" />
                    <stop offset="100%" stopColor="#0E7A6C" />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="#EAEEF5"
                />
                <XAxis
                  dataKey="name"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: "#64748B" }}
                />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: "#94A3B8" }}
                />
                <Tooltip
                  cursor={{ fill: "rgba(43,92,230,0.05)" }}
                  contentStyle={chartTooltipStyle}
                />
                <Bar dataKey="value" fill="url(#sp-bar)" radius={[8, 8, 2, 2]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="sp-card sp-rise sp-d4 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold">失败分类分布</h3>
            <span className="font-mono text-xs text-slate-400">最近执行记录</span>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={failureData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={62}
                  outerRadius={96}
                  paddingAngle={4}
                  cornerRadius={6}
                  stroke="none"
                >
                  {failureData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={chartTooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
        <section className="sp-card sp-rise sp-d5 overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h3 className="text-sm font-semibold">最近执行</h3>
            <Link
              href="/runs"
              className="text-sm font-medium text-run transition-colors hover:text-brand"
            >
              查看全部
            </Link>
          </div>
          {runs.length === 0 ? (
            <div className="px-5 py-10">
              <div className="sp-empty">暂无执行记录</div>
            </div>
          ) : (
            <div className="divide-y divide-line">
              {runs.slice(0, 5).map((run) => (
                <div
                  key={run.run_id}
                  className="grid grid-cols-[1fr_120px_120px] items-center px-5 py-3 text-sm transition-colors hover:bg-slate-50/70"
                >
                  <Link
                    href={`/runs/${run.run_id}`}
                    className="truncate font-mono text-[13px] font-semibold text-ink hover:text-run"
                  >
                    {run.run_id}
                  </Link>
                  <StatusBadge value={run.status} />
                  <span className="text-right font-mono text-xs text-slate-500">
                    {formatDuration(run.duration_ms)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="sp-panel-dark sp-rise sp-d6 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">执行控制台</h3>
            <span className="flex items-center gap-1.5">
              <i className="h-2 w-2 rounded-full bg-fail/80" />
              <i className="h-2 w-2 rounded-full bg-warn/80" />
              <i className="h-2 w-2 rounded-full bg-pass/80" />
            </span>
          </div>
          <div className="mt-4 space-y-2.5 font-mono text-[13px]">
            <ConsoleLine icon={<CheckCircle2 size={15} />} text="executor=browser-use" />
            <ConsoleLine icon={<Play size={15} />} text={`text_model=${model}`} />
            <ConsoleLine icon={<Clock3 size={15} />} text={`avg_duration=${avgDuration}`} />
            <ConsoleLine icon={<ShieldCheck size={15} />} text="scenario_mode=zero-locator" />
            <div className="flex items-center gap-2 px-3 pt-1 text-emerald-300/90">
              <span className="text-slate-500">$</span>
              <span className="sp-pulse inline-block h-3.5 w-[7px] bg-emerald-300/80" />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
  icon,
  delay,
}: {
  label: string;
  value: string;
  hint: string;
  icon: ReactNode;
  delay: string;
}) {
  return (
    <article className={`sp-card sp-card-hover sp-rise ${delay} p-5`}>
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{label}</p>
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-soft text-brand">
          {icon}
        </span>
      </div>
      <p className="sp-num mt-3 text-3xl font-semibold tracking-tight">
        {value}
      </p>
      <p className="mt-2 text-xs text-slate-400">{hint}</p>
    </article>
  );
}

function ActionLink({
  href,
  icon,
  children,
}: {
  href: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <Link href={href} className="sp-btn">
      {icon}
      {children}
    </Link>
  );
}

function ConsoleLine({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-white/[0.04] px-3 py-2 ring-1 ring-white/[0.06]">
      <span className="text-emerald-300/90">{icon}</span>
      <span className="text-slate-200">{text}</span>
    </div>
  );
}

function StatusBadge({ value }: { value: string }) {
  const color =
    statusColors[value as keyof typeof statusColors] ?? statusColors.queued;
  return (
    <span
      className="sp-chip"
      style={{ borderColor: `${color}30`, backgroundColor: `${color}10`, color }}
    >
      <span className="sp-chip-dot" />
      {value}
    </span>
  );
}

function summarizeFailures(runs: Run[]) {
  const counts = new Map<string, number>();
  runs.forEach((run) => {
    if (run.failure_primary) {
      counts.set(run.failure_primary, (counts.get(run.failure_primary) ?? 0) + 1);
    }
  });
  const entries = Array.from(counts.entries());
  if (entries.length === 0) {
    return [{ name: "暂无失败", value: 1, color: "#D8DfEA" }];
  }
  const palette = ["#DF3340", "#B26205", "#2B5CE6", "#0E7A6C", "#7C3AED"];
  return entries.map(([name, value], index) => ({
    name,
    value,
    color: palette[index % palette.length],
  }));
}

function averageDuration(runs: Run[]) {
  const values = runs
    .map((run) => run.duration_ms)
    .filter((value): value is number => typeof value === "number");
  if (values.length === 0) {
    return "--";
  }
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
  return formatDuration(avg);
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
