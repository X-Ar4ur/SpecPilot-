# SpecPilot

SpecPilot is a local full-stack system for generating and executing manual-driven web test scenarios for 4ga Boards.

The source requirements are in `项目需求.md`. The architecture blueprint is in `PLANv2.md`. Agentic workers must read `AGENTS.md` before implementation.

## MVP Stack

- Frontend: Next.js App Router, TypeScript, Tailwind CSS, Radix UI, Lucide Icons, React Flow, TanStack Query, Zustand, Recharts.
- Backend: FastAPI, SQLModel, SQLite, ChromaDB, LangGraph.
- Browser execution: browser-use only.
- Text LLM: DeepSeek V4 Pro (`deepseek-v4-pro`) via `langchain-deepseek` by default.
- Optional text LLM: Browser Use hosted LLM via `BROWSER_USE_API_KEY`, when explicitly selected.
- Vision verification: GLM-4.6V via backend adapter.

## Repository Layout

The implementation plan expects this structure:

```text
frontend/                  Next.js App Router console
backend/                   FastAPI service and agent workflow
docs/                      Requirements, specs, API, schemas, prompts, tests
data/                      Local runtime data, ignored by git
artifacts/                 Optional exported reports, ignored by git
image/                     Existing project assets
```

## Local Environment

Create a `.env` file from `.env.example` before running the app.

Use the project-level uv environment at the repository root:

```bash
uv venv --python 3.12 .venv
uv sync
```

## Start The App Locally

Open two terminals.

Terminal 1, run the backend from the repository root:

```bash
uv run uvicorn specpilot_backend.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, run the Chinese control console:

```bash
cd frontend
pnpm dev --hostname 127.0.0.1 --port 3002
```

Then open the app at:

```text
http://127.0.0.1:3000
```

Seed the local demo acceptance scenarios:

```bash
uv run python -m specpilot_backend.scripts.seed_demo
```

The frontend proxies `/api/*` to `http://127.0.0.1:8000` through `next.config.mjs` when `NEXT_PUBLIC_API_BASE_URL` is not set. Keep Browser Use hosted LLM as an explicit optional text provider or fallback only; setting `BROWSER_USE_API_KEY` must not enable Browser Use Cloud Browser.

## Local Acceptance

Check local readiness:

```bash
uv run python -m specpilot_backend.scripts.seed_demo
uv run uvicorn specpilot_backend.main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/api/doctor
```

Run the automated acceptance gate:

```bash
uv run pytest
uv run ruff check .
uv run pyright

cd frontend
pnpm lint
pnpm typecheck
pnpm build
```

Manual E2E acceptance still requires real 4ga demo credentials, live 4ga access, DeepSeek V4 Pro credentials for text generation or execution, and GLM-4.6V credentials for visual verification. Generated scenarios must remain zero-locator, and run artifacts must include `trace.jsonl`, `report.json`, and `report.html` under `data/runs/{run_id}/`.

## Agent Handoff

When using Codex or Claude to implement this project, prompt it with:

```text
Read AGENTS.md first, then follow docs/IMPLEMENTATION_PLAN.md milestone by milestone.
Implement only the milestone I request. Do not use Playwright. Use browser-use as the only executor. Keep scenarios zero-locator.
```
