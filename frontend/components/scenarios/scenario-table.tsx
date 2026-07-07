"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Download,
  Eye,
  Filter,
  Loader2,
  Play,
  Search,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { api, ApiError } from "../../lib/api";
import type { ScenarioSummary, TestScenario } from "../../lib/types";
import { FixtureBindingDialog } from "./fixture-binding-dialog";

const priorityLabels = { P0: "P0", P1: "P1", P2: "P2" };
const difficultyLabels = {
  simple: "简单",
  medium: "中等",
  hard: "困难",
};
const reviewLabels = {
  auto_validated: "自动通过",
  needs_review: "待审核",
  rejected: "已拒绝",
};

export function ScenarioTable() {
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [bindingScenarioId, setBindingScenarioId] = useState<string | null>(null);
  const scenariosQuery = useQuery({
    queryKey: ["scenarios", priority, difficulty],
    queryFn: () =>
      api.listScenarios({
        priority,
        difficulty,
      }),
  });
  const filtered = useMemo(
    () => {
      const scenarios = scenariosQuery.data?.items ?? [];
      return scenarios.filter((scenario) => {
        return (
          scenario.title.includes(query) ||
          scenario.scenario_id.includes(query) ||
          scenario.feature_id.includes(query)
        );
      });
    },
    [query, scenariosQuery.data?.items],
  );
  const selectedScenarioQuery = useQuery({
    queryKey: ["scenario", selectedId],
    queryFn: () => api.getScenario(selectedId ?? ""),
    enabled: Boolean(selectedId),
  });
  const runMutation = useMutation({
    mutationFn: (scenarioId: string) => api.createRun([scenarioId]),
    onSuccess: (result) => window.location.assign(result.live_url),
    onError: (error, scenarioId) => {
      if (error instanceof ApiError && error.status === 409) {
        setBindingScenarioId(scenarioId);
      }
    },
  });

  function openDetail(scenarioId: string) {
    setSelectedId(scenarioId);
    setDrawerOpen(true);
  }

  return (
    <div className="space-y-4">
      <div className="sp-rise sp-d1 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[260px] flex-1">
          <Search className="absolute left-3 top-3 text-slate-400" size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索场景、功能点或 ID"
            className="sp-input w-full pl-9"
          />
        </div>
        <SelectFilter
          icon={<Filter size={16} />}
          value={priority}
          onChange={setPriority}
          options={[
            ["", "全部优先级"],
            ["P0", "P0"],
            ["P1", "P1"],
            ["P2", "P2"],
          ]}
        />
        <SelectFilter
          value={difficulty}
          onChange={setDifficulty}
          options={[
            ["", "全部难度"],
            ["simple", "简单"],
            ["medium", "中等"],
            ["hard", "困难"],
          ]}
        />
        <a
          className="sp-btn"
          href={api.scenarioStatusReportUrl()}
          target="_blank"
          rel="noreferrer"
        >
          <Download size={16} />
          <span>导出通过率 HTML</span>
        </a>
      </div>

      <section className="sp-card sp-rise sp-d2 overflow-hidden">
        <div className="grid grid-cols-[1.4fr_0.7fr_0.55fr_0.55fr_0.7fr_0.7fr_120px] border-b border-line bg-slate-50/80 px-4 py-3">
          <span className="sp-th">场景</span>
          <span className="sp-th">功能点</span>
          <span className="sp-th">优先级</span>
          <span className="sp-th">难度</span>
          <span className="sp-th">审核</span>
          <span className="sp-th">最近结果</span>
          <span className="sp-th text-right">操作</span>
        </div>
        {scenariosQuery.isError ? (
          <EmptyRow text="场景接口暂不可用" />
        ) : filtered.length === 0 ? (
          <EmptyRow text="暂无测试场景" />
        ) : (
          <div className="divide-y divide-line">
            {filtered.map((scenario) => (
              <ScenarioRow
                key={scenario.scenario_id}
                scenario={scenario}
                onDetail={() => openDetail(scenario.scenario_id)}
                onRun={() => runMutation.mutate(scenario.scenario_id)}
                running={runMutation.isPending}
              />
            ))}
          </div>
        )}
      </section>

      <Dialog.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="sp-overlay-in fixed inset-0 z-40 bg-ink/35 backdrop-blur-[2px]" />
          <Dialog.Content className="sp-drawer-in fixed bottom-2 right-2 top-2 z-50 flex w-full max-w-[680px] flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-lift">
            <div className="flex h-16 shrink-0 items-center justify-between border-b border-line px-5">
              <div>
                <Dialog.Title className="font-display text-base font-semibold">
                  场景详情
                </Dialog.Title>
                <Dialog.Description className="text-xs text-slate-500">
                  步骤、预期、证据和 JSON
                </Dialog.Description>
              </div>
              <Dialog.Close className="sp-icon-btn">
                <X size={18} />
              </Dialog.Close>
            </div>
            <ScenarioDetail scenario={selectedScenarioQuery.data} loading={selectedScenarioQuery.isLoading} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <FixtureBindingDialog
        scenarioId={bindingScenarioId}
        open={Boolean(bindingScenarioId)}
        onOpenChange={(open) => {
          if (!open) setBindingScenarioId(null);
        }}
        onReady={(scenarioId) => {
          setBindingScenarioId(null);
          runMutation.mutate(scenarioId);
        }}
      />
    </div>
  );
}

function ScenarioRow({
  scenario,
  onDetail,
  onRun,
  running,
}: {
  scenario: ScenarioSummary;
  onDetail: () => void;
  onRun: () => void;
  running: boolean;
}) {
  return (
    <div className="grid grid-cols-[1.4fr_0.7fr_0.55fr_0.55fr_0.7fr_0.7fr_120px] items-center px-4 py-3 text-sm transition-colors hover:bg-slate-50/70">
      <div className="min-w-0 pr-3">
        <p className="truncate font-medium">{scenario.title}</p>
        <p className="mt-1 truncate font-mono text-xs text-slate-400">
          {scenario.scenario_id}
        </p>
      </div>
      <span className="truncate pr-2 font-mono text-xs text-slate-500">
        {scenario.feature_id}
      </span>
      <span>
        <PriorityBadge value={scenario.priority} />
      </span>
      <span className="text-slate-600">{difficultyLabels[scenario.difficulty]}</span>
      <span className="text-slate-600">{reviewLabels[scenario.review_status]}</span>
      <StatusBadge value={scenario.latest_result ?? "queued"} />
      <div className="flex justify-end gap-2">
        <button
          className="sp-icon-btn"
          aria-label="查看详情"
          onClick={onDetail}
        >
          <Eye size={16} />
        </button>
        <button
          className="grid h-9 w-9 place-items-center rounded-xl text-white transition-all duration-200 hover:-translate-y-px hover:shadow-glow disabled:cursor-not-allowed disabled:opacity-60"
          style={{ background: "var(--sp-gradient)" }}
          aria-label="运行场景"
          onClick={onRun}
          disabled={running}
        >
          {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
        </button>
      </div>
    </div>
  );
}

function ScenarioDetail({
  scenario,
  loading,
}: {
  scenario: TestScenario | undefined;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="grid flex-1 place-items-center text-sm text-slate-400">
        加载场景中
      </div>
    );
  }
  if (!scenario) {
    return (
      <div className="grid flex-1 place-items-center text-sm text-slate-400">
        未选择场景
      </div>
    );
  }
  return (
    <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5">
      <section>
        <p className="sp-kicker">{scenario.scenario_id}</p>
        <h2 className="mt-2 font-display text-xl font-semibold">
          {scenario.title}
        </h2>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <Badge>{scenario.priority}</Badge>
          <Badge>{difficultyLabels[scenario.difficulty]}</Badge>
          <Badge>{reviewLabels[scenario.review_status]}</Badge>
          <Badge>{scenario.requires_visual_check ? "视觉验证" : "确定性验证"}</Badge>
        </div>
      </section>

      <DetailSection title="前置条件">
        <OrderedList items={scenario.preconditions} />
      </DetailSection>
      <DetailSection title="步骤">
        <ol className="space-y-2">
          {scenario.steps.map((step) => (
            <li key={step.order} className="flex gap-3 text-sm">
              <span
                className="grid h-6 w-6 shrink-0 place-items-center rounded-lg font-mono text-xs font-semibold text-white"
                style={{ background: "var(--sp-gradient)" }}
              >
                {step.order}
              </span>
              <span className="leading-6">{step.action}</span>
            </li>
          ))}
        </ol>
      </DetailSection>
      <DetailSection title="预期结果">
        <div className="space-y-2">
          {scenario.expectations.map((expectation, index) => (
            <div
              key={`${expectation.type}-${index}`}
              className="rounded-xl border border-line px-3 py-2.5 text-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{expectation.description}</span>
                <span className="rounded-full bg-brand-soft px-2.5 py-1 font-mono text-xs text-brand">
                  {expectation.type}
                </span>
              </div>
              <pre className="mt-2 overflow-auto rounded-lg bg-night p-3 font-mono text-xs leading-5 text-slate-100">
                {JSON.stringify(expectation.params, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      </DetailSection>
      <DetailSection title="手册证据">
        <div className="space-y-2">
          {scenario.evidence_quotes.map((quote) => (
            <blockquote
              key={quote}
              className="rounded-r-xl border-l-2 border-brand bg-brand-soft/60 px-4 py-2.5 text-sm leading-6 text-slate-700"
            >
              {quote}
            </blockquote>
          ))}
        </div>
      </DetailSection>
      <DetailSection title="完整 JSON">
        <pre className="max-h-[360px] overflow-auto rounded-xl bg-night p-4 font-mono text-xs leading-5 text-slate-100">
          {JSON.stringify(scenario, null, 2)}
        </pre>
      </DetailSection>
    </div>
  );
}

function DetailSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function OrderedList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">无</p>;
  }
  return (
    <ul className="space-y-2 text-sm">
      {items.map((item) => (
        <li key={item} className="rounded-xl border border-line px-3 py-2">
          {item}
        </li>
      ))}
    </ul>
  );
}

function SelectFilter({
  value,
  onChange,
  options,
  icon,
}: {
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
  icon?: ReactNode;
}) {
  return (
    <div className="relative">
      {icon ? (
        <span className="absolute left-3 top-3 text-slate-400">{icon}</span>
      ) : null}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`sp-input pr-8 ${icon ? "pl-9" : "pl-3"}`}
      >
        {options.map(([optionValue, label]) => (
          <option key={optionValue} value={optionValue}>
            {label}
          </option>
        ))}
      </select>
    </div>
  );
}

function PriorityBadge({ value }: { value: "P0" | "P1" | "P2" }) {
  const classes =
    value === "P0"
      ? "border-red-200 bg-red-50 text-fail"
      : value === "P1"
        ? "border-amber-200 bg-amber-50 text-warn"
        : "border-slate-200 bg-slate-50 text-slate-500";
  return (
    <span className={`sp-chip font-mono ${classes}`}>
      {priorityLabels[value]}
    </span>
  );
}

function StatusBadge({ value }: { value: string }) {
  const classes =
    value === "pass"
      ? "border-emerald-200 bg-emerald-50 text-pass"
      : value === "fail" || value === "error"
        ? "border-red-200 bg-red-50 text-fail"
        : value === "needs_review"
          ? "border-amber-200 bg-amber-50 text-warn"
          : "border-slate-200 bg-slate-50 text-slate-500";
  return (
    <span className={`sp-chip ${classes}`}>
      <span className="sp-chip-dot" />
      {value}
    </span>
  );
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full border border-line bg-slate-50/70 px-2.5 py-1 text-slate-600">
      {children}
    </span>
  );
}

function EmptyRow({ text }: { text: string }) {
  return (
    <div className="px-4 py-10 text-center text-sm text-slate-400">{text}</div>
  );
}
