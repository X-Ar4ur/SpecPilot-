# SpecPilot Agent Implementation Contract

This file is the highest-priority project instruction for Codex, Claude, or any other agentic worker implementing this repository.

## Required Read Order

Before writing code, read these files in order:

1. `项目需求.md`
2. `PLANv2.md`
3. `docs/REQUIREMENTS.md`
4. `docs/SPEC.md`
5. `docs/API.md`
6. `docs/SCHEMAS.md`
7. `docs/TESTING.md`
8. `docs/PROMPTS.md`
9. `docs/IMPLEMENTATION_PLAN.md`
10. `docs/browser-use.md` (read before any work that touches the browser-use integration, even partially)

If any file conflicts with another file, use this priority order:

1. Direct user instruction in the current conversation
2. `AGENTS.md` / `CLAUDE.md`
3. `PLANv2.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. `docs/API.md` and `docs/SCHEMAS.md`
6. `docs/SPEC.md`
7. `项目需求.md`

Note: `PLANv2.md` is the authoritative architecture and contract source. The `docs/*` files are derived implementation contracts kept in sync with `PLANv2.md`. If a `docs/*` file ever drifts from `PLANv2.md`, treat it as a defect and reconcile by updating the `docs/*` file, not by following the drifted contract.

## Non-Negotiable Architecture

- Frontend: Next.js App Router + TypeScript.
- Backend: FastAPI + SQLModel + SQLite.
- Agent orchestration: LangGraph.
- Browser executor: `browser-use` only.
- Vector store: ChromaDB.
- Text model: DeepSeek V4 Pro (`deepseek-v4-pro`) through `langchain-deepseek` by default.
- Optional text model provider: Browser Use hosted LLM through `BROWSER_USE_API_KEY`, only when explicitly selected in settings.
- Vision verifier: GLM-4.6V through a backend adapter.
- Local artifact storage: filesystem under `data/runs/{run_id}/`.
- UI language: Chinese by default.

## Strict Prohibitions

- Do not use Playwright as an executor, fallback runner, or hidden test agent.
- Do not fork or modify `browser-use`.
- Do not create 4ga Boards domain-specific `browser-use` tools/actions.
- Do not generate or store DOM locators in test scenarios.
- Do not include `selector`, `locator`, `xpath`, `element_id`, `element_index`, or CSS selector fields in scenario schemas.
- Do not implement CDP screencast in MVP. Keep it as a reserved P2 API endpoint only.
- Do not implement the full mutation-generation algorithm in MVP. The MVP exposes mutation schemas and a stub endpoint only.
- Do not put secrets, test account passwords, or API keys in prompts, scenarios, logs, traces, screenshots metadata, or committed files.
- Do not silently replace GLM-4.6V, DeepSeek V4 Pro, LangGraph, browser-use, or the explicitly selected text model provider with other technologies.
- Do not invent `browser-use` APIs, parameters, hooks, action signatures, or model adapter shapes from memory. If unsure, consult `docs/browser-use.md` first; if still unsure, fetch the official documentation at `https://docs.browser-use.com/` before writing code.

## Python Environment Rule

- Use `uv` to manage the Python environment at the **repository root**. There is exactly one project-level virtual environment: `<repo-root>/.venv`.
- Do not create per-subdirectory virtual environments (no `backend/.venv`, no `frontend/.venv`, no global `pip install`).
- The Python project (`pyproject.toml`, `uv.lock`) lives at the repository root. Source code lives under `backend/src/specpilot_backend/`. Tests live under `backend/tests/`.
- All Python commands run from the repository root via `uv run <cmd>` (e.g. `uv run pytest backend/tests`, `uv run ruff check .`, `uv run uvicorn specpilot_backend.main:app`). Do not `cd backend` before invoking `uv`.
- Pin Python to `>=3.11,<3.13` in `pyproject.toml`. Bootstrap the venv with `uv venv --python 3.12 .venv` and resolve dependencies with `uv sync`.

## browser-use Integration Rule

- `docs/browser-use.md` is the in-repo reference for the `browser-use` library (vendored AGENTS.md + selected official docs). Read it before integrating, debugging, or extending any browser-use behavior.
- If `docs/browser-use.md` does not cover the question, fetch the relevant page from the official documentation at `https://docs.browser-use.com/` (or the upstream repository at `https://github.com/browser-use/browser-use`) before writing code. Do not guess at API shapes, configuration keys, or sensitive-data injection mechanics.
- This project pins `browser-use>=0.12.6,<0.13`. If the official docs reference newer or older APIs, prefer the behavior consistent with the pinned version, and ask the user before bumping the pin.
- This project's default text model is **DeepSeek V4 Pro** (`deepseek-v4-pro`) via `langchain-deepseek`, and the visual verifier is **GLM-4.6V** via the backend adapter.
- `BROWSER_USE_API_KEY` may be used only as an explicitly selected Browser Use hosted LLM provider or fallback. This changes the LLM provider, not the browser execution mode.
- Do not substitute `use_cloud=True`, `@sandbox`, `cdp_url`, Browser Use Cloud Browser, or any other runtime suggested by upstream browser-use documentation unless the user explicitly changes the MVP architecture.

## Ambiguity Rule

If an implementation detail is missing and guessing would affect architecture, data contracts, security, or user-visible behavior, stop and ask the user. If the detail is small and local, make the most conservative choice, document it in the relevant file, and continue.

## Implementation Rule

Work milestone by milestone. Implement only the milestone requested by the user. Each milestone must finish with:

- passing tests listed in `docs/TESTING.md`;
- updated docs if contracts changed;
- a short summary of files changed and verification commands run.

## MVP Boundary

The MVP must implement:

- manual crawling and indexing for 4ga Boards user/admin manual pages;
- feature extraction;
- zero-locator scenario generation;
- scenario listing and visualization;
- browser-use-driven run execution;
- trace collection;
- deterministic verification;
- GLM-4.6V visual verification adapter;
- failure classification;
- run history and report artifacts;
- Chinese Next.js control console.

The MVP must not implement:

- custom 4ga browser actions;
- Playwright execution;
- CDP video streaming;
- full mutation-generation algorithms;
- cloud deployment.
