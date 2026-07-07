# SpecPilot Testing Contract

Every milestone must run the tests relevant to files changed. Do not claim completion without reporting the exact commands and outcomes.

## Environment

This project uses a single project-level `uv`-managed virtual environment at `<repo-root>/.venv`. All Python commands run from the **repository root** via `uv run <cmd>`. Do not `cd backend` before invoking `uv`. Do not create per-subdirectory virtualenvs.

Bootstrap once:

```bash
uv venv --python 3.12 .venv
uv sync
```

## Backend Commands

Expected backend test command (run from repository root):

```bash
uv run pytest
```

To run a subset of tests, point pytest at the relevant files under `backend/tests/`:

```bash
uv run pytest backend/tests/test_scenario_schema.py
```

Expected backend lint/type commands:

```bash
uv run ruff check .
uv run pyright
```

## Frontend Commands

Expected frontend test command after the Next.js project exists:

```bash
cd frontend
pnpm test
```

Expected frontend quality command:

```bash
cd frontend
pnpm lint
pnpm typecheck
```

Expected frontend build command:

```bash
cd frontend
pnpm build
```

## Required Unit Tests

Backend:

- scenario schema rejects forbidden locator fields;
- feature schema requires source URLs and evidence quotes;
- quote validator rejects quotes absent from source chunks;
- expectation type dispatches to the correct verifier;
- GLM vision verifier adapter parses valid JSON;
- GLM confidence thresholds produce pass/fail/needs_review correctly;
- mutation endpoint returns a valid stub schema.
- settings endpoint writes model settings to `.env`, never returns secret values, preserves existing API keys when submitted empty, and rejects `browser_use_cloud_browser_enabled=true` in the MVP.
- fixture schema rejects forbidden locator fields inside `fixtures`, and `data_dependency` defaults to `none`;
- template-token resolution replaces `{{fixture.<ref>.<attr>}}` in steps, test_data, and expectations with bound values, leaving no unresolved token;
- ScenarioFixtureBinding persists and is isolated per `target_app_url`;
- FourgaApiClient logs in, lists the Project/Board/List/Card inventory, and creates a card against a mocked 4ga REST API, and never leaks the token;
- a run with unestablished preconditions reports `status=error` and `failure_primary=precondition_setup_failure`, excluded from functional metrics.

Frontend:

- navigation renders all required routes;
- manual generation page renders readiness checks, crawl/index/feature/scenario phases, production job state, result statistics, and success/error actions;
- scenario table renders steps, expectations, evidence, and JSON detail;
- live run page handles `node_status`, `browser_step`, `browser_frame`, `verification`, and `classification` events;
- settings form exposes one OpenAI-compatible text model configuration, supports preset field filling, and saves without exposing secret values.
- fixture-binding modal renders the inventory tree, supports selecting an existing element and creating a new one, shows remembered bindings, and re-prompts when a bound element is missing.

## Required Integration Tests

- crawl/index pipeline stores user/admin manual chunks and excludes developer manual pages;
- manual-to-scenarios pipeline reports a background job, replaces demo data only after success, and preserves existing data on failure;
- feature extraction returns at least 8 features when model credentials are configured;
- scenario generation returns zero-locator scenarios with evidence;
- creating a run creates a database record and artifact directory;
- SSE stream emits trace-compatible events;
- report generation writes `report.json` and `report.html`.
- scenario status report exports all scenarios to HTML, omits scenario ids, and calculates pass rate with all scenarios as the denominator.
- `GET /api/fixtures/inventory` returns a Project→Board→List→Card tree for the configured instance;
- `POST /api/fixtures/bind` persists a binding (existing and create modes) and rebinds the scenario's action target and expectation params;
- launching an `interactive` scenario without a valid binding is rejected with its unbound slots.

## Required Configuration Tests

- default text provider is `openai_compatible`;
- default OpenAI-compatible model is `gpt-5.5`;
- default DeepSeek model is `deepseek-v4-pro`;
- `OPENAI_COMPATIBLE_API_KEY` may be empty at startup, but selected-provider readiness reports a Doctor warning until configured;
- `BROWSER_USE_API_KEY` is optional unless `TEXT_LLM_PROVIDER=browser_use` or Browser Use LLM fallback is enabled;
- Browser Use hosted LLM selection does not enable Browser Use Cloud Browser, `use_cloud=True`, `@sandbox`, or `cdp_url`.

## Required E2E Acceptance

When credentials and model keys are configured, run these scenarios through browser-use only:

- create board and verify its name is visible;
- create list and verify the list is visible;
- create card and verify the card appears in the target list;
- edit card title/description and verify the update;
- drag card to another list and verify containment;
- switch board/list view and verify visual state.

## Manual Acceptance Targets

- at least 8 features;
- at least 16 valid scenarios;
- simple scenario pass rate >= 80%;
- medium scenario pass rate >= 60%;
- at least 6 failure categories represented in real or seeded failure examples;
- all generated scenarios remain zero-locator.

## Manual Generation Page Acceptance

The frontend exposes a standalone `/manual-generation` route in the sidebar as `手册生成`.

The page must show:

- readiness checks for text model, GLM vision, browser-use, ChromaDB, SQLite, and artifact storage;
- four production phases: `抓取手册`, `索引证据`, `提取功能点`, and `生成场景`;
- latest job id, status, progress, result counts, zero-locator state, and error summary;
- action links to feature tree, scenario table, and a first P0 scenario run when available.

## Milestone 9 Local Acceptance Checklist

Run from the repository root unless noted:

```bash
uv run python -m specpilot_backend.scripts.seed_demo
uv run uvicorn specpilot_backend.main:app --host 127.0.0.1 --port 8000
```

Then check:

- `GET /api/doctor` reports database, ChromaDB persist dir, artifact root, browser-use install state, model key status, and `browser_use_cloud_browser` as disabled for MVP;
- the seeded demo set includes the six required E2E acceptance scenarios: create board, create list, create card, edit card, drag card, and switch view;
- every generated or seeded scenario passes the zero-locator validator;
- Browser Use hosted LLM remains an optional text provider/fallback only and never enables Browser Use Cloud Browser, `use_cloud=True`, `@sandbox`, or `cdp_url`;
- each completed run has `trace.jsonl`, `report.json`, and `report.html` under `data/runs/{run_id}/`;
- the run detail page exposes report export links for JSON and HTML when those files exist.

The six browser-use E2E scenarios require real 4ga demo credentials, live network access to 4ga, DeepSeek V4 Pro or explicitly selected Browser Use hosted LLM credentials, and GLM-4.6V credentials when visual checks are required.

## Documentation Checks

Before handing the repo to another agent, run:

```bash
rg -n "TBD|TODO|implement later|fill in|placeholder|待定|后续补充" .
rg -n "selector|locator|xpath|element_index|element_id|css_selector" docs AGENTS.md CLAUDE.md
```

Allowed matches:

- `AGENTS.md`, `PLANv2.md`, `README.md`, `docs/REQUIREMENTS.md`, `docs/SCHEMAS.md`, `docs/PROMPTS.md`, `docs/API.md`, `docs/TESTING.md`, `docs/FIXTURE_PROVISIONING.md`, and tests may mention forbidden locator terms only as prohibitions or validation checks.
- `docs/SPEC.md` and `PLANv2.md` may mention deferred P2 features only as explicit non-MVP scope.
- `docs/browser-use.md` may contain upstream browser-use examples that mention ChatBrowserUse, Browser Use Cloud, Playwright integration, or selectors, but its SpecPilot Project Override at the top controls project behavior.
