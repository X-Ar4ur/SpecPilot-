import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const shellSource = readFileSync(
  new URL("../components/app-shell/app-shell.tsx", import.meta.url),
  "utf8",
);
const apiSource = readFileSync(new URL("../lib/api.ts", import.meta.url), "utf8");
const typesSource = readFileSync(new URL("../lib/types.ts", import.meta.url), "utf8");
const pageUrl = new URL("../app/manual-generation/page.tsx", import.meta.url);

test("sidebar exposes manual generation as a standalone route", () => {
  assert.match(shellSource, /手册生成/);
  assert.match(shellSource, /href: "\/manual-generation"/);
  assert.match(shellSource, /BookOpenCheck|WandSparkles/);
});

test("manual generation API client exposes pipeline and job calls", () => {
  assert.match(typesSource, /export type JobStatus/);
  assert.match(typesSource, /export type PipelineStartResponse/);
  assert.match(typesSource, /export type ManualPipelineResult/);
  assert.match(apiSource, /startManualPipeline/);
  assert.match(apiSource, /\/api\/pipeline\/manual-to-scenarios/);
  assert.match(apiSource, /getJob/);
  assert.match(apiSource, /\/api\/jobs\/\$\{jobId\}/);
  assert.match(typesSource, /ManualPipelineStartStage/);
  assert.match(typesSource, /ManualPipelinePage/);
  assert.match(typesSource, /ManualPipelineWarning/);
  assert.match(typesSource, /start_stage/);
  assert.match(typesSource, /resume_from_job_id/);
  assert.match(apiSource, /startManualPipeline\(payload/);
});

test("manual generation page renders detailed production pipeline state", () => {
  assert.equal(existsSync(pageUrl), true);
  const pageSource = readFileSync(pageUrl, "utf8");

  assert.match(pageSource, /抓取手册/);
  assert.match(pageSource, /索引证据/);
  assert.match(pageSource, /提取功能点/);
  assert.match(pageSource, /生成场景/);
  assert.match(pageSource, /readiness|就绪检查/);
  assert.match(pageSource, /有效功能点|features_count/);
  assert.match(pageSource, /有效场景|scenarios_count/);
  assert.match(pageSource, /零 locator|zero_locator/);
  assert.match(pageSource, /查看功能点/);
  assert.match(pageSource, /查看测试场景/);
  assert.match(pageSource, /运行 P0 场景/);
});

test("manual generation page exposes staged actions and intermediate artifacts", () => {
  assert.equal(existsSync(pageUrl), true);
  const pageSource = readFileSync(pageUrl, "utf8");

  assert.match(pageSource, /从头执行/);
  assert.match(pageSource, /执行索引/);
  assert.match(pageSource, /执行提取/);
  assert.match(pageSource, /执行场景生成/);
  assert.match(pageSource, /start_stage: "index"/);
  assert.match(pageSource, /start_stage: "features"/);
  assert.match(pageSource, /start_stage: "scenarios"/);
  assert.match(pageSource, /resume_from_job_id/);
  assert.match(pageSource, /已抓取页面/);
  assert.match(pageSource, /已提取功能点/);
  assert.match(pageSource, /诊断信息/);
  assert.match(pageSource, /warnings/);
});
