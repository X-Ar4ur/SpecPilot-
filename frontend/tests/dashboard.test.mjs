import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");

test("dashboard console text model comes from runtime settings", () => {
  assert.match(source, /queryKey: \["settings"\]/);
  assert.match(source, /text_model=\$\{model\}/);
  assert.equal(source.includes('text="text_model=deepseek-v4-pro"'), false);
});
