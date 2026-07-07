"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ExternalLink, Filter, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "../../lib/api";
import type { Feature, FeatureModule } from "../../lib/types";

const moduleOrder: FeatureModule[] = [
  "Project",
  "Board",
  "List",
  "Card",
  "Views",
  "Settings",
  "Admin",
  "Other",
];

const moduleLabels: Record<FeatureModule, string> = {
  Project: "Project",
  Board: "Board",
  List: "List",
  Card: "Card",
  Views: "Views",
  Settings: "Settings",
  Admin: "Admin",
  Other: "Other",
};

const coverageLabels = {
  covered: "已覆盖",
  partial: "部分覆盖",
  uncovered: "未覆盖",
};

export function FeatureTree() {
  const [query, setQuery] = useState("");
  const [coverage, setCoverage] = useState<string>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedModules, setExpandedModules] = useState<
    Partial<Record<FeatureModule, boolean>>
  >({});
  const featuresQuery = useQuery({
    queryKey: ["features"],
    queryFn: api.listFeatures,
  });
  const filtered = useMemo(
    () => {
      const features = featuresQuery.data?.items ?? [];
      return features.filter((feature) => {
        const matchesQuery =
          feature.title.includes(query) ||
          feature.summary.includes(query) ||
          feature.module.includes(query);
        const matchesCoverage =
          coverage === "all" || feature.coverage_status === coverage;
        return matchesQuery && matchesCoverage;
      });
    },
    [featuresQuery.data?.items, query, coverage],
  );
  const grouped = useMemo(() => {
    return moduleOrder.map((module) => ({
      module,
      items: filtered
        .filter((feature) => feature.module === module)
        .sort((left, right) => right.confidence - left.confidence),
    }));
  }, [filtered]);
  const selected =
    filtered.find((feature) => feature.feature_id === selectedId) ??
    filtered[0] ??
    null;
  const searching = query.trim().length > 0;
  const isOpen = (module: FeatureModule) => {
    const override = expandedModules[module];
    if (override !== undefined) return override;
    // 搜索时自动展开命中的类别；否则默认仅展开当前选中功能点所在的类别
    if (searching) return true;
    return module === selected?.module;
  };
  const toggleModule = (module: FeatureModule) => {
    setExpandedModules((current) => ({
      ...current,
      [module]: !isOpen(module),
    }));
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
      <section className="sp-rise sp-d1 space-y-4 xl:sticky xl:top-20 xl:self-start">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 text-slate-400" size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索模块、功能点、摘要"
              className="sp-input w-full pl-9"
            />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-3 text-slate-400" size={16} />
            <select
              value={coverage}
              onChange={(event) => setCoverage(event.target.value)}
              className="sp-input pl-9 pr-8"
            >
              <option value="all">全部覆盖</option>
              <option value="covered">已覆盖</option>
              <option value="partial">部分覆盖</option>
              <option value="uncovered">未覆盖</option>
            </select>
          </div>
        </div>

        <div className="sp-card overflow-hidden">
          <div className="max-h-[calc(100vh-12rem)] overflow-y-auto overscroll-contain">
          {featuresQuery.isError ? (
            <EmptyMessage text="功能点接口暂不可用" />
          ) : filtered.length === 0 ? (
            <EmptyMessage text="暂无功能点数据" />
          ) : (
            <div className="divide-y divide-line">
              {grouped
                .filter((group) => group.items.length > 0)
                .map((group) => {
                  const open = isOpen(group.module);
                  return (
                    <div key={group.module} className="py-2">
                      <button
                        type="button"
                        onClick={() => toggleModule(group.module)}
                        aria-expanded={open}
                        className="flex w-full items-center justify-between gap-2 rounded-lg px-4 py-1.5 text-left transition-colors duration-200 hover:bg-slate-50"
                      >
                        <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                          {moduleLabels[group.module]}
                        </span>
                        <span className="flex items-center gap-2 text-slate-400">
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
                            {group.items.length}
                          </span>
                          <ChevronDown
                            size={15}
                            className={`transition-transform duration-200 ${
                              open ? "" : "-rotate-90"
                            }`}
                          />
                        </span>
                      </button>
                      {open ? (
                        <div className="mt-1 space-y-1 px-2">
                          {group.items.map((feature) => {
                            const active =
                              selected?.feature_id === feature.feature_id;
                            return (
                              <button
                                key={feature.feature_id}
                                onClick={() => setSelectedId(feature.feature_id)}
                                className={`w-full rounded-xl px-3 py-2 text-left text-sm transition-all duration-200 ${
                                  active
                                    ? "text-white shadow-glow"
                                    : "hover:bg-slate-50"
                                }`}
                                style={
                                  active
                                    ? { background: "var(--sp-gradient)" }
                                    : undefined
                                }
                              >
                                <span className="block font-medium">
                                  {feature.title}
                                </span>
                                <span
                                  className={`mt-1 block text-xs ${
                                    active ? "text-white/80" : "text-slate-400"
                                  }`}
                                >
                                  {coverageLabels[feature.coverage_status]} ·{" "}
                                  {Math.round(feature.confidence * 100)}%
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
            </div>
          )}
          </div>
        </div>
      </section>

      <FeatureDetail feature={selected} />
    </div>
  );
}

function FeatureDetail({ feature }: { feature: Feature | null }) {
  if (!feature) {
    return (
      <section className="sp-rise sp-d2 rounded-2xl border border-dashed border-slate-200 bg-white/60 p-6 text-sm text-slate-400">
        选择一个功能点查看证据、覆盖状态和关联信息。
      </section>
    );
  }

  return (
    <section className="sp-card sp-rise sp-d2 min-w-0 space-y-5 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="sp-kicker">{feature.module}</p>
          <h2 className="mt-2 font-display text-xl font-semibold">
            {feature.title}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            {feature.summary}
          </p>
        </div>
        <span className="sp-chip border-line bg-slate-50 text-slate-600">
          {coverageLabels[feature.coverage_status]}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Metric label="证据数量" value={String(feature.evidence_quotes.length)} />
        <Metric label="来源 URL" value={String(feature.source_urls.length)} />
        <Metric label="置信度" value={`${Math.round(feature.confidence * 100)}%`} />
      </div>

      <section>
        <h3 className="mb-3 text-sm font-semibold">手册证据</h3>
        <div className="space-y-2">
          {feature.evidence_quotes.map((quote) => (
            <blockquote
              key={quote}
              className="rounded-r-xl border-l-2 border-brand bg-brand-soft/60 px-4 py-2.5 text-sm leading-6 text-slate-700"
            >
              {quote}
            </blockquote>
          ))}
        </div>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-semibold">来源</h3>
        <div className="space-y-2">
          {feature.source_urls.map((url) => (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 font-mono text-xs text-run transition-all duration-200 hover:-translate-y-px hover:border-slate-300 hover:shadow-card"
            >
              <ExternalLink size={15} className="shrink-0" />
              <span className="min-w-0 truncate">{url}</span>
            </a>
          ))}
        </div>
      </section>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-slate-50/70 p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="sp-num mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function EmptyMessage({ text }: { text: string }) {
  return (
    <div className="px-4 py-8 text-center text-sm text-slate-400">{text}</div>
  );
}
