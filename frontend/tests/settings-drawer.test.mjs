import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../components/app-shell/settings-drawer.tsx", import.meta.url),
  "utf8",
);
const typesSource = readFileSync(new URL("../lib/types.ts", import.meta.url), "utf8");

test("settings drawer uses one OpenAI-compatible provider form", () => {
  assert.equal(source.includes("@radix-ui/react-tabs"), false);
  assert.equal(source.includes("<Tabs.Root"), false);
  assert.match(source, /供应商名称/);
  assert.match(source, /官网链接/);
  assert.match(source, /API Key/);
  assert.match(source, /API 请求地址/);
  assert.match(source, /模型名称/);
});

test("settings drawer offers presets without provider tabs", () => {
  assert.match(source, /Codex API \/ 中转站/);
  assert.match(source, /OpenAI/);
  assert.match(source, /DeepSeek/);
});

test("runtime settings types include OpenAI-compatible fields", () => {
  assert.match(typesSource, /"openai_compatible"/);
  assert.match(typesSource, /openai_compatible_provider_name: string/);
  assert.match(typesSource, /openai_compatible_base_url: string/);
  assert.match(typesSource, /openai_compatible_model: string/);
  assert.match(typesSource, /openai_compatible_api_key_configured: boolean/);
  assert.match(typesSource, /openai_compatible_api_key\?: string \| null/);
});
