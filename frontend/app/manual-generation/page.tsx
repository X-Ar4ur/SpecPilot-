"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  FileSearch,
  ListChecks,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import type { DoctorCheck, Feature, Job, JobStatus } from "../../lib/types";

type PhaseId = "crawl" | "index" | "features" | "scenarios";

const phases: Array<{
  id: PhaseId;
  label: string;
  detail: string;
  icon: typeof FileSearch;
}> = [
  {
    id: "crawl",
    label: "抓取手册",
    detail: "限定英文 user/admin manual，排除开发者与技术页面。",
    icon: FileSearch,
  },
  {
    id: "index",
    label: "索引证据",
    detail: "按标题切块，写入 ChromaDB，并保留 evidence manifest。",
    icon: Database,
  },
  {
    id: "features",
    label: "提取功能点",
    detail: "使用当前文本模型抽取能力级 Feature，并校验证据 quote。",
    icon: Sparkles,
  },
  {
    id: "scenarios",
    label: "生成场景",
    detail: "为功能点生成自然语言步骤与结构化预期，执行零 locator 校验。",
    icon: ListChecks,
  },
];

const statusLabels: Record<JobStatus, string> = {
  queued: "排队中",
  running: "运行中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export default function ManualGenerationPage() {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const doctorQuery = useQuery({
    queryKey: ["doctor"],
    queryFn: api.getDoctor,
  });
  const scenariosQuery = useQuery({
    queryKey: ["scenarios", "p0"],
    queryFn: () => api.listScenarios({ priority: "P0" }),
  });
  const featuresQuery = useQuery({
    queryKey: ["features"],
    queryFn: api.listFeatures,
  });
  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId ?? ""),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1600 : false;
    },
  });
  const startMutation = useMutation({
    mutationFn: api.startManualPipeline,
    onSuccess: (result) => {
      setJobId(result.job_id);
      void queryClient.invalidateQueries({ queryKey: ["doctor"] });
    },
  });
  const runP0Mutation = useMutation({
    mutationFn: async () => {
      const scenarioId = scenariosQuery.data?.items[0]?.scenario_id;
      if (!scenarioId) {
        throw new Error("暂无 P0 场景");
      }
      return api.createRun([scenarioId]);
    },
    onSuccess: (result) => window.location.assign(result.live_url),
  });
  const job = jobQuery.data;
  const isBusy =
    startMutation.isPending ||
    job?.status === "queued" ||
    job?.status === "running";
  const result = job?.result;
  const resultFeatures = result?.features ?? [];
  const savedFeatures = featuresQuery.data?.items ?? [];
  const canRunIndex = Boolean(result?.crawl_id);
  const canRunFeatures = Boolean(result?.index_id);
  const canRunScenarios = resultFeatures.length > 0 || savedFeatures.length > 0;
  const stageActions = {
    crawl: () => startMutation.mutate({ start_stage: "crawl" }),
    index: () =>
      startMutation.mutate({
        start_stage: "index",
        resume_from_job_id: job?.job_id,
        crawl_id: result?.crawl_id,
      }),
    features: () =>
      startMutation.mutate({
        start_stage: "features",
        resume_from_job_id: job?.job_id,
        index_id: result?.index_id,
      }),
    scenarios: () =>
      startMutation.mutate({
        start_stage: "scenarios",
        resume_from_job_id: job?.job_id,
        index_id: result?.index_id,
        feature_ids: resultFeatures.map((feature) => feature.feature_id),
      }),
  };
  const phaseActionMeta = {
    crawl: { label: "从头执行", disabled: isBusy },
    index: { label: "执行索引", disabled: isBusy || !canRunIndex },
    features: { label: "执行提取", disabled: isBusy || !canRunFeatures },
    scenarios: { label: "执行场景生成", disabled: isBusy || !canRunScenarios },
  };
  const readinessItems = useMemo(
    () => readinessSummary(doctorQuery.data?.checks ?? {}),
    [doctorQuery.data?.checks],
  );

  useEffect(() => {
    if (job?.status === "succeeded") {
      void queryClient.invalidateQueries({ queryKey: ["features"] });
      void queryClient.invalidateQueries({ queryKey: ["scenarios"] });
      void queryClient.invalidateQueries({ queryKey: ["doctor"] });
    }
  }, [job?.status, queryClient]);

  return (
    <div className="space-y-6">
      <header className="sp-rise flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="sp-kicker">Manual Generation</p>
          <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight">
            真实手册生成
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            从 4ga Boards 英文用户/管理员手册生成可执行、证据对齐、零 locator 的测试资产。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="sp-btn-primary"
            onClick={() => stageActions.crawl()}
            disabled={isBusy}
          >
            {isBusy ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            从头执行真实生成
          </button>
          <LinkButton href="/features" icon={<FileSearch size={16} />}>
            查看功能点
          </LinkButton>
          <LinkButton href="/scenarios" icon={<ListChecks size={16} />}>
            查看测试场景
          </LinkButton>
          <button
            className="sp-btn"
            onClick={() => runP0Mutation.mutate()}
            disabled={runP0Mutation.isPending || !scenariosQuery.data?.items.length}
          >
            <Play size={16} />
            运行 P0 场景
          </button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {readinessItems.map((item, index) => (
          <ReadinessTile
            key={item.label}
            {...item}
            delay={`sp-d${Math.min(index + 1, 6)}`}
          />
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-4">
        {phases.map((phase, index) => (
          <PhaseCard
            key={phase.id}
            phase={phase}
            index={index}
            job={job}
            loading={startMutation.isPending}
            actionLabel={phaseActionMeta[phase.id].label}
            actionDisabled={phaseActionMeta[phase.id].disabled}
            onRun={stageActions[phase.id]}
          />
        ))}
      </section>

      <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
        <section className="sp-card sp-rise sp-d3 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
            <div>
              <h3 className="text-sm font-semibold">最近 job</h3>
              <p className="mt-1 font-mono text-xs text-slate-400">
                {job ? job.job_id : "尚未启动真实手册生成"}
              </p>
            </div>
            <JobBadge status={job?.status ?? "queued"} muted={!job} />
          </div>
          <div className="space-y-5 px-5 py-5">
            <ProgressBar value={job?.progress ?? 0} />
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Stat label="页面" value={result?.pages_count} />
              <Stat label="证据块" value={result?.chunks_count} />
              <Stat label="有效功能点" value={result?.features_count} />
              <Stat label="有效场景" value={result?.scenarios_count} />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <InfoRow label="抓取范围" value="docs.4gaboards.com / docs/user-manual + docs/admin-manual / en" />
              <InfoRow
                label="零 locator 校验"
                value={result?.zero_locator ? "通过" : "等待生成结果"}
              />
              <InfoRow label="数据替换" value={result?.replaced_existing ? "已替换 demo 普通场景" : "成功后自动替换"} />
              <InfoRow label="当前阶段" value={job?.stage ?? "未开始"} />
            </div>
            {job?.error ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-fail">
                <div className="font-semibold">失败原因</div>
                <div className="mt-1 leading-6">{job.error || "未知异常"}</div>
              </div>
            ) : null}
            {job?.status === "succeeded" ? (
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-pass">
                <CheckCircle2 size={17} />
                真实生成已完成，功能点和普通测试场景已刷新为手册产物。
              </div>
            ) : null}
          </div>
        </section>

        <section className="sp-card sp-rise sp-d4 overflow-hidden">
          <div className="border-b border-line px-5 py-4">
            <h3 className="text-sm font-semibold">已抓取页面</h3>
            <p className="mt-1 text-xs text-slate-400">
              抓取阶段完成后会在这里显示页面标题、模块和 URL。
            </p>
          </div>
          <div className="max-h-[360px] overflow-auto px-5 py-4">
            {result?.pages?.length ? (
              <div className="space-y-2">
                {result.pages.map((page) => (
                  <a
                    key={page.url}
                    href={page.url}
                    target="_blank"
                    rel="noreferrer"
                    className="grid gap-1 rounded-xl border border-line px-3 py-2.5 text-sm transition-all duration-200 hover:-translate-y-px hover:border-slate-300 hover:shadow-card"
                  >
                    <span className="font-medium text-ink">{page.title}</span>
                    <span className="text-xs text-slate-400">
                      {page.module} / {page.manual_section}
                    </span>
                    <span className="break-all font-mono text-xs text-run">
                      {page.url}
                    </span>
                  </a>
                ))}
              </div>
            ) : (
              <EmptyState text="暂无抓取页面，先执行抓取手册。" />
            )}
          </div>
        </section>

        <section className="sp-card sp-rise sp-d5 overflow-hidden">
          <div className="border-b border-line px-5 py-4">
            <h3 className="text-sm font-semibold">已提取功能点</h3>
            <p className="mt-1 text-xs text-slate-400">
              提取阶段完成后会显示本次 job 的功能点预览。
            </p>
          </div>
          <div className="max-h-[420px] overflow-auto px-5 py-4">
            {resultFeatures.length ? (
              <FeaturePreviewList features={resultFeatures} />
            ) : (
              <EmptyState text="暂无本次 job 功能点，先执行提取功能点。" />
            )}
          </div>
        </section>

        <section className="sp-card sp-rise sp-d5 overflow-hidden">
          <div className="border-b border-line px-5 py-4">
            <h3 className="text-sm font-semibold">诊断信息</h3>
            <p className="mt-1 text-xs text-slate-400">
              warnings 和失败 error 会集中显示，便于判断是否可继续从中间阶段重跑。
            </p>
          </div>
          <div className="space-y-3 px-5 py-4">
            {result?.warnings?.length ? (
              result.warnings.map((warning, index) => (
                <div
                  key={`${warning.stage}-${warning.scope}-${index}`}
                  className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-warn"
                >
                  <div className="font-mono text-xs font-semibold">
                    {warning.stage} / {warning.scope}
                  </div>
                  <div className="mt-1 leading-5">{warning.message || "未知异常"}</div>
                </div>
              ))
            ) : (
              <EmptyState text="暂无 warning。" />
            )}
            {job?.error ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-fail">
                <div className="font-semibold">失败 error</div>
                <div className="mt-1 leading-5">{job.error || "未知异常"}</div>
              </div>
            ) : null}
          </div>
        </section>

        <section className="sp-panel-dark sp-rise sp-d6 p-5">
          <h3 className="text-sm font-semibold">生产路径约束</h3>
          <div className="mt-4 space-y-2.5 text-[13px]">
            <ConsoleLine icon={<ShieldCheck size={15} />} text="scenario_mode=zero-locator" />
            <ConsoleLine icon={<Database size={15} />} text="vector_store=ChromaDB" />
            <ConsoleLine icon={<FileSearch size={15} />} text="scope=user/admin manual only" />
            <ConsoleLine icon={<Sparkles size={15} />} text="generation=model-driven evidence quotes" />
          </div>
          <div className="mt-5 border-t border-white/10 pt-4">
            <h4 className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              产物入口
            </h4>
            <div className="mt-3 grid gap-2">
              <DarkLink href="/features">功能点树 <ArrowRight size={14} /></DarkLink>
              <DarkLink href="/scenarios">测试场景 <ArrowRight size={14} /></DarkLink>
              <DarkLink href="/runs">执行记录 <ArrowRight size={14} /></DarkLink>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function readinessSummary(checks: Record<string, DoctorCheck>) {
  return [
    {
      label: "文本模型",
      check: checks.openai_compatible_api ?? checks.deepseek_api ?? checks.browser_use_llm,
    },
    { label: "GLM 视觉", check: checks.glm_vision_api },
    { label: "browser-use", check: checks.browser_use },
    { label: "ChromaDB", check: checks.chroma },
    { label: "SQLite/Artifacts", check: checks.database ?? checks.artifact_root },
  ].map((item) => ({
    label: item.label,
    status: item.check?.status ?? "warning",
    detail: item.check?.detail ?? "等待就绪检查",
  }));
}

function ReadinessTile({
  label,
  status,
  detail,
  delay,
}: {
  label: string;
  status: string;
  detail: string;
  delay: string;
}) {
  const classes =
    status === "ok"
      ? "border-emerald-200/80 bg-emerald-50/80 text-pass"
      : status === "error"
        ? "border-red-200/80 bg-red-50/80 text-fail"
        : "border-amber-200/80 bg-amber-50/80 text-warn";
  return (
    <article
      className={`sp-rise ${delay} rounded-2xl border px-4 py-3 shadow-card backdrop-blur-sm transition-transform duration-200 hover:-translate-y-0.5 ${classes}`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold">{label}</span>
        {status === "ok" ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
      </div>
      <p className="mt-2 line-clamp-2 text-xs leading-5 opacity-80">{detail}</p>
    </article>
  );
}

function PhaseCard({
  phase,
  index,
  job,
  loading,
  actionLabel,
  actionDisabled,
  onRun,
}: {
  phase: (typeof phases)[number];
  index: number;
  job: Job | undefined;
  loading: boolean;
  actionLabel: string;
  actionDisabled: boolean;
  onRun: () => void;
}) {
  const Icon = phase.icon;
  const state = phaseState(phase.id, job, loading);
  return (
    <article
      className={`sp-card sp-card-hover sp-rise sp-d${Math.min(index + 1, 6)} relative overflow-hidden p-5`}
    >
      <span className="sp-num pointer-events-none absolute -right-1 -top-4 select-none text-[64px] font-bold leading-none text-slate-100">
        0{index + 1}
      </span>
      <div className="relative flex items-start justify-between gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-soft text-brand">
          <Icon size={18} />
        </div>
      </div>
      <h3 className="relative mt-4 font-display text-base font-semibold">
        {phase.label}
      </h3>
      <p className="relative mt-2 min-h-10 text-sm leading-5 text-slate-500">
        {phase.detail}
      </p>
      <div className="relative mt-4 flex items-center gap-2 text-sm">
        {state === "running" ? <Loader2 size={15} className="animate-spin text-run" /> : null}
        {state === "done" ? <CheckCircle2 size={15} className="text-pass" /> : null}
        {state === "failed" ? <AlertTriangle size={15} className="text-fail" /> : null}
        {state === "pending" ? <Clock3 size={15} className="text-slate-400" /> : null}
        <span
          className={
            state === "running"
              ? "font-medium text-run"
              : state === "done"
                ? "font-medium text-pass"
                : state === "failed"
                  ? "font-medium text-fail"
                  : "text-slate-400"
          }
        >
          {phaseStateLabel(state)}
        </span>
      </div>
      <button
        className="sp-btn relative mt-4 h-9 w-full"
        onClick={onRun}
        disabled={actionDisabled}
      >
        <Play size={15} />
        {actionLabel}
      </button>
    </article>
  );
}

function phaseState(phaseId: string, job: Job | undefined, loading: boolean) {
  if (loading) {
    return phaseId === "crawl" ? "running" : "pending";
  }
  if (!job) {
    return "pending";
  }
  if (job.status === "failed") {
    return job.stage === phaseId ? "failed" : "pending";
  }
  if (job.status === "succeeded") {
    return "done";
  }
  const order = phases.findIndex((phase) => phase.id === phaseId);
  const current = phases.findIndex((phase) => phase.id === job.stage);
  if (order < current) {
    return "done";
  }
  if (order === current) {
    return "running";
  }
  return "pending";
}

function phaseStateLabel(value: string) {
  if (value === "running") return "运行中";
  if (value === "done") return "已完成";
  if (value === "failed") return "失败";
  return "等待中";
}

function JobBadge({ status, muted }: { status: JobStatus; muted?: boolean }) {
  const classes =
    status === "succeeded"
      ? "border-emerald-200 bg-emerald-50 text-pass"
      : status === "failed"
        ? "border-red-200 bg-red-50 text-fail"
        : status === "running"
          ? "border-blue-200 bg-blue-50 text-run"
          : "border-slate-200 bg-slate-50 text-slate-500";
  return (
    <span className={`sp-chip ${classes} ${muted ? "opacity-60" : ""}`}>
      <span className={`sp-chip-dot ${status === "running" && !muted ? "sp-pulse" : ""}`} />
      {muted ? "未启动" : statusLabels[status]}
    </span>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
        <span>总体进度</span>
        <span className="font-mono">{value}%</span>
      </div>
      <div className="sp-progress-track">
        <div className="sp-progress-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-xl border border-line bg-slate-50/70 px-3 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="sp-num mt-1 text-2xl font-semibold">{value ?? "--"}</p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line px-3 py-3 text-sm">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 break-words font-medium">{value}</div>
    </div>
  );
}

function FeaturePreviewList({ features }: { features: Feature[] }) {
  return (
    <div className="space-y-2">
      {features.map((feature) => (
        <article
          key={feature.feature_id}
          className="rounded-xl border border-line px-3 py-3 transition-colors hover:bg-slate-50/70"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">{feature.title}</h4>
            <span className="sp-chip border-slate-200 bg-slate-50 text-slate-600">
              {feature.module} / {Math.round(feature.confidence * 100)}%
            </span>
          </div>
          <p className="mt-2 text-sm leading-5 text-slate-500">{feature.summary}</p>
          <div className="mt-2 text-xs text-slate-400">
            证据 {feature.evidence_quotes.length} 条
          </div>
          <div className="mt-2 space-y-1">
            {feature.source_urls.map((url) => (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="block break-all font-mono text-xs text-run hover:underline"
              >
                {url}
              </a>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="sp-empty">{text}</div>;
}

function LinkButton({
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
    <div className="flex items-center gap-2 rounded-lg bg-white/[0.04] px-3 py-2 font-mono ring-1 ring-white/[0.06]">
      <span className="text-emerald-300/90">{icon}</span>
      <span className="text-slate-200">{text}</span>
    </div>
  );
}

function DarkLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between rounded-lg bg-white/[0.04] px-3 py-2 text-sm text-slate-200 ring-1 ring-white/[0.06] transition-all duration-200 hover:translate-x-0.5 hover:bg-white/[0.09] hover:text-white"
    >
      {children}
    </Link>
  );
}
