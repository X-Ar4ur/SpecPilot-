"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Plus, X } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { api } from "../../lib/api";
import type {
  FixtureInventory,
  FixtureKind,
  FixtureSlotBindingState,
} from "../../lib/types";

const kindLabels: Record<FixtureKind, string> = {
  project: "Project",
  board: "Board",
  list: "List",
  card: "Card",
};

type Candidate = {
  id: string;
  name: string;
  path: string;
  attributes: Record<string, string>;
};

// Flatten the Project -> Board -> List -> Card inventory tree to the elements
// of a single kind. Each candidate carries the full attribute set a fixture
// token may reference (title/name + ancestor names) so bindings resolve every
// token, not just the title.
function candidatesForKind(
  inventory: FixtureInventory | undefined,
  kind: FixtureKind,
): Candidate[] {
  const out: Candidate[] = [];
  for (const project of inventory?.projects ?? []) {
    if (kind === "project") {
      out.push({
        id: project.id,
        name: project.name,
        path: "",
        attributes: {
          name: project.name,
          title: project.name,
          middle_text: project.name,
        },
      });
      continue;
    }
    for (const board of project.boards) {
      if (kind === "board") {
        out.push({
          id: board.id,
          name: board.name,
          path: project.name,
          attributes: {
            name: board.name,
            title: board.name,
            middle_text: board.name,
            project_name: project.name,
          },
        });
        continue;
      }
      for (const list of board.lists) {
        const listPath = `${project.name} / ${board.name}`;
        if (kind === "list") {
          out.push({
            id: list.id,
            name: list.name,
            path: listPath,
            attributes: {
              name: list.name,
              title: list.name,
              middle_text: list.name,
              board_name: board.name,
              project_name: project.name,
              card_count: String(list.cards.length),
            },
          });
          continue;
        }
        for (const card of list.cards) {
          out.push({
            id: card.id,
            name: card.name,
            path: `${listPath} / ${list.name}`,
            attributes: {
              title: card.name,
              name: card.name,
              list_name: list.name,
              board_name: board.name,
              project_name: project.name,
            },
          });
        }
      }
    }
  }
  return out;
}

export function FixtureBindingDialog({
  scenarioId,
  open,
  onOpenChange,
  onReady,
}: {
  scenarioId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onReady: (scenarioId: string) => void;
}) {
  const queryClient = useQueryClient();
  const bindingQuery = useQuery({
    queryKey: ["binding", scenarioId],
    queryFn: () => api.getScenarioBinding(scenarioId ?? ""),
    enabled: open && Boolean(scenarioId),
  });
  const inventoryQuery = useQuery({
    queryKey: ["fixture-inventory"],
    queryFn: () => api.getFixtureInventory(),
    enabled: open,
  });

  const status = bindingQuery.data;
  const ready = status?.ready ?? false;

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["binding", scenarioId] });
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="sp-overlay-in fixed inset-0 z-40 bg-ink/35 backdrop-blur-[2px]" />
        <Dialog.Content className="sp-drawer-in fixed bottom-2 right-2 top-2 z-50 flex w-full max-w-[640px] flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-lift">
          <div className="flex h-16 shrink-0 items-center justify-between border-b border-line px-5">
            <div>
              <Dialog.Title className="font-display text-base font-semibold">
                绑定测试数据
              </Dialog.Title>
              <Dialog.Description className="text-xs text-slate-500">
                此场景依赖既有数据，请为每个目标选择或新建元素
              </Dialog.Description>
            </div>
            <Dialog.Close className="sp-icon-btn">
              <X size={18} />
            </Dialog.Close>
          </div>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
            {bindingQuery.isLoading || inventoryQuery.isLoading ? (
              <p className="text-sm text-slate-400">加载绑定状态中…</p>
            ) : inventoryQuery.isError ? (
              <p className="text-sm text-fail">
                无法获取 4ga 实例元素，请检查目标实例配置（FOURGA_API_BASE_URL）。
              </p>
            ) : (
              (status?.slots ?? []).map((slot) => (
                <SlotBinder
                  key={slot.ref}
                  scenarioId={scenarioId ?? ""}
                  slot={slot}
                  inventory={inventoryQuery.data}
                  onBound={refresh}
                />
              ))
            )}
          </div>

          <div className="flex h-16 shrink-0 items-center justify-between border-t border-line px-5">
            <span className="text-xs text-slate-500">
              {ready ? "全部已绑定" : "尚有目标未绑定"}
            </span>
            <button
              className="rounded-xl px-4 py-2 text-sm font-medium text-white transition-all disabled:cursor-not-allowed disabled:opacity-50"
              style={{ background: "var(--sp-gradient)" }}
              disabled={!ready || !scenarioId}
              onClick={() => scenarioId && onReady(scenarioId)}
            >
              开始运行
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function SlotBinder({
  scenarioId,
  slot,
  inventory,
  onBound,
}: {
  scenarioId: string;
  slot: FixtureSlotBindingState;
  inventory: FixtureInventory | undefined;
  onBound: () => void;
}) {
  const [mode, setMode] = useState<"existing" | "create">("existing");
  const [newTitle, setNewTitle] = useState("");
  const [parentId, setParentId] = useState("");
  const bindMutation = useMutation({
    mutationFn: api.bindFixture,
    onSuccess: onBound,
  });

  const candidates = candidatesForKind(inventory, slot.kind);
  const lists = candidatesForKind(inventory, "list");
  const selectedList = lists.find((list) => list.id === parentId);
  const boundValue =
    slot.binding?.resolved_values?.title ?? slot.binding?.resolved_values?.name;
  const boundTitle =
    typeof boundValue === "string" ? boundValue : slot.binding?.entity_id;

  return (
    <section className="rounded-xl border border-line p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="sp-chip font-mono">{kindLabels[slot.kind]}</span>
          <span className="font-mono text-xs text-slate-500">{slot.ref}</span>
        </div>
        {slot.exists ? (
          <span className="inline-flex items-center gap-1 text-xs text-pass">
            <Check size={14} /> 已绑定：{boundTitle}
          </span>
        ) : slot.bound ? (
          <span className="text-xs text-warn">原绑定已失效，请重新绑定</span>
        ) : (
          <span className="text-xs text-slate-400">未绑定</span>
        )}
      </header>

      <div className="mt-3 flex gap-2">
        <ModeButton
          active={mode === "existing"}
          onClick={() => setMode("existing")}
        >
          选择已有
        </ModeButton>
        {slot.kind === "card" ? (
          <ModeButton
            active={mode === "create"}
            onClick={() => setMode("create")}
          >
            新建
          </ModeButton>
        ) : null}
      </div>

      {mode === "existing" ? (
        <div className="mt-3 max-h-56 space-y-1 overflow-y-auto">
          {candidates.length === 0 ? (
            <p className="text-xs text-slate-400">实例中暂无该类型元素</p>
          ) : (
            candidates.map((candidate) => (
              <button
                key={candidate.id}
                className="flex w-full items-center justify-between rounded-lg border border-line px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                disabled={bindMutation.isPending}
                onClick={() =>
                  bindMutation.mutate({
                    scenario_id: scenarioId,
                    ref: slot.ref,
                    mode: "existing",
                    kind: slot.kind,
                    entity_id: candidate.id,
                    attributes: candidate.attributes,
                  })
                }
              >
                <span className="truncate">{candidate.name}</span>
                {candidate.path ? (
                  <span className="ml-2 shrink-0 truncate font-mono text-[11px] text-slate-400">
                    {candidate.path}
                  </span>
                ) : null}
              </button>
            ))
          )}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <input
            value={newTitle}
            onChange={(event) => setNewTitle(event.target.value)}
            placeholder="新元素标题"
            className="sp-input w-full"
          />
          <select
            value={parentId}
            onChange={(event) => setParentId(event.target.value)}
            className="sp-input w-full"
          >
            <option value="">选择所属 List</option>
            {lists.map((list) => (
              <option key={list.id} value={list.id}>
                {list.path} / {list.name}
              </option>
            ))}
          </select>
          <button
            className="inline-flex items-center gap-1 rounded-lg border border-line px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
            disabled={!newTitle || !parentId || bindMutation.isPending}
            onClick={() =>
              bindMutation.mutate({
                scenario_id: scenarioId,
                ref: slot.ref,
                mode: "create",
                kind: "card",
                parent_id: parentId,
                attributes: {
                  title: newTitle,
                  name: newTitle,
                  list_name: selectedList?.name ?? "",
                  board_name: selectedList?.attributes.board_name ?? "",
                  project_name: selectedList?.attributes.project_name ?? "",
                },
              })
            }
          >
            {bindMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Plus size={14} />
            )}
            创建并绑定
          </button>
        </div>
      )}
      {bindMutation.isError ? (
        <p className="mt-2 text-xs text-fail">绑定失败，请重试</p>
      ) : null}
    </section>
  );
}

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
        active ? "bg-brand text-white" : "border border-line text-slate-600"
      }`}
    >
      {children}
    </button>
  );
}
