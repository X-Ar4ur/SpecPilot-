# SpecPilot Product and Architecture Spec

`PLANv2.md` is the full architecture narrative. This file is the concise implementation spec that agents should use while coding.

## Architecture

```text
Next.js Console
  -> REST + SSE
FastAPI Backend
  -> SQLModel / SQLite metadata
  -> ChromaDB manual index
  -> LangGraph workflow
  -> browser-use Agent using configured text LLM
  -> deterministic verifier + GLM-4.6V verifier
  -> filesystem artifacts
```

## Model Providers

- Default text provider: OpenAI-compatible / Codex API via `OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_API_KEY`, and `OPENAI_COMPATIBLE_MODEL`.
- Legacy text providers remain readable for compatibility: DeepSeek V4 Pro via `langchain-deepseek`, and Browser Use hosted LLM via `BROWSER_USE_API_KEY` and `BROWSER_USE_MODEL` only when explicitly selected.
- Browser execution mode remains local browser-use Managed Browser in MVP. Selecting Browser Use hosted LLM must not enable Browser Use Cloud Browser, `use_cloud=True`, `@sandbox`, or `cdp_url`.
- Vision verifier: GLM-4.6V through the backend adapter.

## Frontend

Use Next.js App Router with TypeScript.

Routes:

```text
/                         Dashboard
/features                 Feature tree
/scenarios                Scenario table
/runs/live/[run_id]       Live execution
/runs                     Run history
/runs/[run_id]            Run detail
```

Layout:

- top bar: product name, global run status, model status, notifications, settings button;
- collapsible left navigation: workbench, features, scenarios, live runs, run history;
- main content area: current route.
- settings drawer: one OpenAI-compatible provider form with provider name, note, home URL, write-only API key, API request base URL, and model name; presets may fill Codex API / gateway, OpenAI, or DeepSeek defaults without adding provider tabs. Existing secrets must be shown only as configured/empty states.
- fixture-binding modal: shown when launching a data-dependent scenario (non-empty `fixtures`); lists the target instance's existing Project/Board/List/Card elements and lets the user pick an existing element or create a new one. Bindings are remembered per `target_app_url`; re-runs skip the modal when the bound element still exists.

Visual direction:

- Chinese UI;
- professional testing console;
- high information density;
- light main interface with dark live execution console areas;
- status colors: green pass, red fail, amber warning, blue running.

Required frontend libraries:

- Tailwind CSS;
- Radix UI;
- Lucide Icons;
- React Flow;
- TanStack Query;
- Zustand;
- Recharts.
- @microsoft/fetch-event-source for SSE.

Framer Motion is allowed for small UI transitions but must not block MVP.

## Backend

Use FastAPI with SQLModel and SQLite.

Responsibilities:

- crawl and index manual content;
- extract features;
- generate scenarios;
- persist feature/scenario/run metadata;
- run LangGraph workflow;
- stream live run events through SSE;
- expose artifact files safely under the configured artifact root;
- generate JSON and HTML reports.

## Agent Workflow

LangGraph nodes:

```text
ScenarioLoader
FixtureResolver
BrowserUseRun
TraceCollector
DeterministicVerifier
VisionVerifier
FailureClassifier
RepairPlanner
Reporter
```

Responsibility split:

- browser-use performs the per-scenario browser planning and execution loop;
- LangGraph orchestrates loading, execution handoff, trace collection, verification, classification, repair decision, and reporting.
- FixtureResolver establishes data preconditions for data-dependent scenarios before execution: it resolves remembered bindings or opens the frontend binding modal, lists/creates target elements through the 4ga REST API, and injects resolved values into steps/test_data/expectations. See `docs/FIXTURE_PROVISIONING.md`.

The implementation must not build a separate LLM planner that duplicates browser-use internal planning.

## RAG

Crawl scope:

- English user manual;
- English admin manual;
- UI operation pages only;
- exclude developer manual and non-UI technical material.

Chunking:

- split by Markdown headers first;
- use recursive character splitting only when a header chunk is too large;
- target 400 tokens with 50 token overlap.

Metadata:

- URL;
- title;
- heading path;
- manual section;
- language;
- UI operational classification;
- content hash.

Retrieval:

- use ChromaDB for vector search;
- feature extraction may use broad context when the indexed manual corpus is small enough;
- scenario generation must cite evidence chunks.

## Artifacts

Runtime artifacts are stored under:

```text
data/runs/{run_id}/
  trace.jsonl
  report.json
  report.html
  screenshots/
  dom/
  verification/
```

SQLite stores metadata and indexes. The filesystem stores large artifacts. They are connected by `run_id`.

## Verification

Deterministic verifier handles:

- `element_visible`;
- `text_present`;
- `url_match`;
- `element_state`;
- `containment`.

Vision verifier handles:

- `semantic`;
- any scenario with `requires_visual_check=true`;
- final whole-page visual sanity check when configured.

Verdicts:

- `pass`;
- `fail`;
- `needs_review`.

A run whose fixture preconditions cannot be established (4ga API unreachable, login failure, or binding cancelled with no usable element) ends with `status = error` and `failure_primary = precondition_setup_failure`. This environment-blocked outcome is excluded from the functional pass/fail and failure-category metrics.

Confidence thresholds:

- high: `0.85`;
- low: `0.60`.

## MVP Boundaries

Implement now:

- full main path from crawl to run report;
- mutation schema and stub endpoint;
- screencast API reserved endpoint only.

Defer:

- CDP screencast implementation;
- full mutation-generation algorithms;
- cloud deployment;
- custom browser-use actions.
