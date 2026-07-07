"use client";

import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "reactflow";

import type { TraceEvent } from "../../lib/types";

const stages = [
  { id: "ScenarioLoader", label: "ScenarioLoader", x: 0, y: 0 },
  { id: "BrowserUseRun", label: "BrowserUseRun", x: 210, y: 0 },
  { id: "TraceCollector", label: "TraceCollector", x: 420, y: 0 },
  {
    id: "DeterministicVerifier",
    label: "DeterministicVerifier",
    x: 630,
    y: -70,
  },
  { id: "VisionVerifier", label: "GLM-4.6V VisionVerifier", x: 630, y: 70 },
  { id: "FailureClassifier", label: "FailureClassifier", x: 860, y: 0 },
  { id: "RepairPlanner", label: "RepairPlanner", x: 1090, y: -70 },
  { id: "Reporter", label: "Reporter", x: 1090, y: 70 },
];

const aliases: Record<string, string> = {
  "GLM-4.6V VisionVerifier": "VisionVerifier",
  GLMVisionVerifier: "VisionVerifier",
  DeterministicVerifierNode: "DeterministicVerifier",
  VisionVerifierNode: "VisionVerifier",
  BrowserUseRunNode: "BrowserUseRun",
  FailureClassifierNode: "FailureClassifier",
  ReporterNode: "Reporter",
};

const statusClasses: Record<string, string> = {
  pending: "border-slate-200 bg-white text-slate-500",
  queued: "border-slate-200 bg-white text-slate-500",
  running: "border-blue-300 bg-blue-50 text-run ring-4 ring-blue-100/60",
  success: "border-emerald-300 bg-emerald-50 text-pass",
  pass: "border-emerald-300 bg-emerald-50 text-pass",
  failed: "border-red-300 bg-red-50 text-fail",
  fail: "border-red-300 bg-red-50 text-fail",
  error: "border-red-300 bg-red-50 text-fail",
  skipped: "border-slate-200 bg-slate-50 text-slate-400",
  retrying: "border-amber-300 bg-amber-50 text-warn",
  needs_review: "border-amber-300 bg-amber-50 text-warn",
};

export function AgentFlow({ events }: { events: TraceEvent[] }) {
  const stageStatus = new Map<string, string>();
  events
    .filter((event) => event.type === "node_status" || event.type === "verification" || event.type === "classification" || event.type === "report")
    .forEach((event) => {
      const nodeId = normalizeNode(event.node ?? stringPayload(event, "node"));
      if (nodeId) {
        stageStatus.set(nodeId, event.status ?? stringPayload(event, "status") ?? "running");
      }
    });

  const nodes: Node[] = stages.map((stage) => {
    const status = stageStatus.get(stage.id) ?? "pending";
    return {
      id: stage.id,
      position: { x: stage.x, y: stage.y },
      data: {
        label: (
          <div className="min-w-[150px]">
            <div className="font-mono text-xs font-semibold">{stage.label}</div>
            <div className="mt-1 text-[11px] opacity-70">{status}</div>
          </div>
        ),
      },
      className: `rounded-xl border px-3 py-2 text-sm shadow-card transition-all duration-300 ${statusClasses[status] ?? statusClasses.pending}`,
      type: "default",
    };
  });

  const edges: Edge[] = [
    ["ScenarioLoader", "BrowserUseRun"],
    ["BrowserUseRun", "TraceCollector"],
    ["TraceCollector", "DeterministicVerifier"],
    ["TraceCollector", "VisionVerifier"],
    ["DeterministicVerifier", "FailureClassifier"],
    ["VisionVerifier", "FailureClassifier"],
    ["FailureClassifier", "RepairPlanner"],
    ["FailureClassifier", "Reporter"],
    ["RepairPlanner", "Reporter"],
  ].map(([source, target]) => ({
    id: `${source}-${target}`,
    source,
    target,
    animated:
      stageStatus.get(source) === "running" || stageStatus.get(target) === "running",
    markerEnd: { type: MarkerType.ArrowClosed, color: "#94A3B8" },
    style: { stroke: "#A8B4C6", strokeWidth: 1.5 },
  }));

  return (
    <section className="sp-card sp-rise sp-d2 h-[320px] overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background gap={20} color="#DDE4EE" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </section>
  );
}

function normalizeNode(node: string | null | undefined) {
  if (!node) {
    return null;
  }
  return aliases[node] ?? node;
}

function stringPayload(event: TraceEvent, key: string) {
  const value = event.payload[key];
  return typeof value === "string" ? value : null;
}
