import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../components/app-shell/app-shell.tsx", import.meta.url),
  "utf8",
);

test("header does not render the sidebar toggle button", () => {
  assert.equal(source.includes('aria-label="切换侧边栏"'), false);
  assert.equal(source.includes("PanelLeft"), false);
});

test("header does not render the long product subtitle", () => {
  assert.equal(source.includes("手册驱动 Web 测试控制台"), false);
});

test("header renders the brand from the repository logo image", () => {
  assert.match(source, /import logo from ["']\.\.\/\.\.\/\.\.\/image\/logo\.png["'];/);
  assert.match(source, /<img/);
  assert.match(source, /src=\{logo\.src\}/);
  assert.equal(source.includes("Activity"), false);
});

test("sidebar uses a compact light surface with larger blue active navigation", () => {
  assert.match(source, /bg-white/);
  assert.match(source, /collapsed \? "w-\[64px\]" : "w-\[184px\]"/);
  assert.match(source, /collapsed \? "pl-\[64px\]" : "pl-\[184px\]"/);
  assert.match(source, /text-\[15px\]/);
  assert.match(source, /min-w-0 truncate/);
  assert.match(source, /bg-blue-50 text-run/);
  assert.equal(source.includes("bg-[#172033]"), false);
  assert.equal(source.includes("text-slate-200 hover:bg-white/10"), false);
});

test("run history is not active for live run process routes", () => {
  assert.equal(source.includes("pathname.startsWith(item.href)"), false);
  assert.match(source, /return pathname === href;/);
});

test("live run child routes keep the run process navigation active", () => {
  assert.match(source, /isNavigationActive\(pathname, item\.href\)/);
  assert.match(source, /href === "\/runs\/live"/);
  assert.match(source, /pathname\.startsWith\("\/runs\/live\/"\)/);
});
