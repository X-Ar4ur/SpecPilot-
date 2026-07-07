import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../components/scenarios/scenario-table.tsx", import.meta.url),
  "utf8",
);

test("running a scenario performs a full navigation to the live run URL", () => {
  assert.match(source, /window\.location\.assign\(result\.live_url\)/);
  assert.equal(source.includes("router.push(result.live_url)"), false);
});
