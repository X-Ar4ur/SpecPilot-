import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dialog = readFileSync(
  new URL(
    "../components/scenarios/fixture-binding-dialog.tsx",
    import.meta.url,
  ),
  "utf8",
);
const table = readFileSync(
  new URL("../components/scenarios/scenario-table.tsx", import.meta.url),
  "utf8",
);

test("binding dialog reads binding status and the inventory tree", () => {
  assert.match(dialog, /api\.getScenarioBinding/);
  assert.match(dialog, /api\.getFixtureInventory/);
  // Flattens the full Project -> Board -> List -> Card tree.
  assert.match(dialog, /project\.boards/);
  assert.match(dialog, /board\.lists/);
  assert.match(dialog, /list\.cards/);
});

test("binding dialog supports selecting existing and creating new elements", () => {
  assert.match(dialog, /api\.bindFixture/);
  assert.match(dialog, /mode: "existing"/);
  assert.match(dialog, /mode: "create"/);
  assert.match(dialog, /选择已有/);
  assert.match(dialog, /新建/);
});

test("binding dialog shows remembered bindings and re-prompts when stale", () => {
  assert.match(dialog, /已绑定/);
  assert.match(dialog, /已失效/);
});

test("binding dialog captures full element attributes, not just title", () => {
  // Bindings must carry list_name/board_name/project_name so every fixture
  // token resolves, not only {{fixture.ref.title}}.
  assert.match(dialog, /attributes: candidate\.attributes/);
  assert.match(dialog, /list_name: list\.name/);
  assert.match(dialog, /board_name: board\.name/);
});

test("binding dialog sends compatibility aliases for legacy fixture tokens", () => {
  assert.match(dialog, /title: board\.name/);
  assert.match(dialog, /title: list\.name/);
  assert.match(dialog, /middle_text: project\.name/);
  assert.match(dialog, /card_count: String\(list\.cards\.length\)/);
});

test("binding dialog runs only once all slots are ready", () => {
  assert.match(dialog, /开始运行/);
  assert.match(dialog, /disabled=\{!ready/);
  assert.match(dialog, /onReady\(scenarioId\)/);
});

test("scenario table opens the binding dialog on a 409 gating response", () => {
  assert.match(table, /import \{ api, ApiError \}/);
  assert.match(table, /error instanceof ApiError && error\.status === 409/);
  assert.match(table, /setBindingScenarioId/);
  assert.match(table, /<FixtureBindingDialog/);
});
