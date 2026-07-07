# SpecPilot API Contract

All API paths are served by the FastAPI backend. JSON is UTF-8. Datetimes use ISO 8601 UTC strings.

## Ingestion

### `POST /api/ingestion/crawl`

Starts or refreshes the manual crawl.

Request:

```json
{
  "base_url": "https://docs.4gaboards.com/",
  "sections": ["user-manual", "admin-manual"],
  "language": "en"
}
```

Response:

```json
{
  "crawl_id": "crawl_20260506_001",
  "status": "queued"
}
```

### `POST /api/ingestion/index`

Indexes crawled manual chunks into ChromaDB.

Request:

```json
{
  "crawl_id": "crawl_20260506_001",
  "force": false
}
```

Response:

```json
{
  "index_id": "idx_20260506_001",
  "status": "queued"
}
```

## Features

### `POST /api/features/extract`

Extracts feature points from indexed manual evidence.

Request:

```json
{
  "index_id": "idx_20260506_001",
  "min_evidence": 1
}
```

Response:

```json
{
  "job_id": "job_features_001",
  "status": "queued"
}
```

### `GET /api/features`

Response:

```json
{
  "items": [
    {
      "feature_id": "ft_card_creation",
      "module": "Card",
      "title": "创建 Card",
      "summary": "用户可以在指定 List 中创建 Card。",
      "source_urls": ["https://docs.4gaboards.com/cards/create"],
      "evidence_quotes": ["在 List 中点击 Add Card 即可创建新的卡片。"],
      "coverage_status": "covered",
      "confidence": 0.91
    }
  ]
}
```

## Scenarios

### `POST /api/scenarios/generate`

Generates zero-locator test scenarios from extracted features.

Request:

```json
{
  "feature_ids": ["ft_card_creation"],
  "max_scenarios_per_feature": 3
}
```

Response:

```json
{
  "job_id": "job_scenarios_001",
  "status": "queued"
}
```

### `GET /api/scenarios`

Query parameters:

- `feature_id`;
- `priority`;
- `difficulty`;
- `review_status`;
- `latest_result`;
- `is_mutation`.

Response:

```json
{
  "items": [
    {
      "scenario_id": "sc_create_card_001",
      "feature_id": "ft_card_creation",
      "title": "在指定 List 中创建新 Card",
      "priority": "P0",
      "difficulty": "simple",
      "review_status": "auto_validated",
      "latest_result": "pass",
      "is_mutation": false
    }
  ]
}
```

### `GET /api/scenarios/{scenario_id}`

Returns the full scenario schema defined in `docs/SCHEMAS.md`.

### `GET /api/scenarios/status-report.html`

Exports the latest pass/fail status of all scenarios as an HTML table.

Rules:

- the pass rate denominator is all scenarios, not only executed scenarios;
- rows must not include `scenario_id`;
- `latest_result = pass` is displayed as passed;
- `latest_result = fail` is displayed as failed;
- `latest_result = needs_review` is displayed as pending review;
- missing `latest_result` is displayed as not run.

## Fixtures

These endpoints back the interactive fixture-binding modal for data-dependent scenarios. The backend reaches the target 4ga Boards instance through `FourgaApiClient`, reusing the configured `fourga_username` / `fourga_password`. The 4ga login token is never returned to the frontend, logs, traces, or reports.

### `GET /api/fixtures/inventory`

Lists the existing elements of the target instance as a Project → Board → List → Card tree for the binding modal. Optional `kind` query filters to one entity type.

Response:

```json
{
  "target_app_url": "http://localhost:1337/",
  "projects": [
    {
      "id": "1799990033768252426",
      "name": "Getting started",
      "boards": [
        {
          "id": "1799990034514838542",
          "name": "Learn 4ga Boards",
          "lists": [
            {
              "id": "1799990037459239957",
              "name": "Getting Started",
              "cards": [
                { "id": "1799990037618623521", "name": "Getting Started" }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### `POST /api/fixtures/bind`

Binds a scenario fixture slot to an element. `mode = "existing"` binds to an element the user picked; `mode = "create"` creates a new element through the 4ga REST API and binds to it.

Request:

```json
{
  "scenario_id": "sc_list_view_card_open_001",
  "ref": "target_card",
  "mode": "create",
  "kind": "card",
  "parent_id": "1799990037459239957",
  "attributes": { "title": "完成季度报告" }
}
```

Response returns the persisted `ScenarioFixtureBinding` from `docs/SCHEMAS.md` (no secret values).

### `GET /api/scenarios/{scenario_id}/binding`

Returns the current bindings for a scenario against the active `target_app_url`, including a per-slot `exists` flag from a live 4ga existence check. Slots without a valid binding signal that the modal must be shown.

## Jobs

### `GET /api/jobs/{job_id}`

Returns the current state of a background job created by crawl, index, feature extraction, scenario generation, or the full manual pipeline.

Response:

```json
{
  "job_id": "job_20260520_001",
  "job_type": "manual_pipeline",
  "status": "running",
  "stage": "features",
  "progress": 60,
  "message": "正在基于手册证据提取功能点",
  "result": {
    "crawl_id": "crawl_20260520_001",
    "pages_count": 24,
    "chunks_count": 88
  },
  "error": null,
  "created_at": "2026-05-20T01:00:00+00:00",
  "started_at": "2026-05-20T01:00:01+00:00",
  "finished_at": null
}
```

`status` is one of `queued`, `running`, `succeeded`, `failed`, or `cancelled`.

## Manual Pipeline

### `POST /api/pipeline/manual-to-scenarios`

Runs the production manual generation path:

```text
crawl -> chunk/index -> extract features -> generate scenarios
```

Request fields are optional and default to the approved 4ga English user/admin manual scope:

```json
{
  "base_url": "https://docs.4gaboards.com/",
  "sections": ["user-manual", "admin-manual"],
  "language": "en",
  "max_pages": 250,
  "max_scenarios_per_feature": 3
}
```

Response:

```json
{
  "job_id": "job_20260520_001",
  "status": "queued"
}
```

On success, the job result includes `crawl_id`, `index_id`, `pages_count`, `chunks_count`, `features_count`, `scenarios_count`, `zero_locator`, and `replaced_existing`. The successful pipeline replaces existing non-mutation features and scenarios with the newly generated manual-grounded output. On failure, existing data is preserved.

## Runs

### `POST /api/runs`

Creates a run for one or more scenarios.

Request:

```json
{
  "scenario_ids": ["sc_create_card_001"],
  "mode": "single",
  "config": {
    "max_steps": 20,
    "retry_limit": 1
  }
}
```

Response:

```json
{
  "run_id": "run_20260506_001",
  "status": "queued",
  "live_url": "/runs/live/run_20260506_001"
}
```

For a scenario with `data_dependency = "interactive"`, every fixture slot must have a valid binding before the run starts; otherwise the backend rejects the request and returns the unbound slots so the frontend can open the binding modal. A run whose preconditions cannot be established finishes with `status = error` and `failure_primary = precondition_setup_failure` (see `docs/SCHEMAS.md`).

### `GET /api/runs`

Returns paginated run metadata for the history table.

### `GET /api/runs/{run_id}`

Returns run summary, verification result, failure classification, and report links.

### `GET /api/runs/{run_id}/events`

SSE stream. Event payloads use `TraceEvent` from `docs/SCHEMAS.md`.

### `GET /api/runs/{run_id}/trace`

Returns `trace.jsonl` as structured JSON lines or a parsed array.

### `GET /api/runs/{run_id}/artifacts`

Lists the artifact tree for the run.

### `GET /api/runs/{run_id}/artifacts/{path}`

Returns a file under `data/runs/{run_id}/`. The backend must reject path traversal.

### `GET /api/runs/{run_id}/report?format=json|html|pdf`

Downloads a generated report file from `data/runs/{run_id}/`.

- `json` serves `report.json`;
- `html` serves `report.html`;
- `pdf` is accepted only when `report.pdf` exists. The MVP does not generate PDF by default.

Missing report files return `404`. This endpoint is only a file export surface; it does not implement cloud storage or deferred report generation.

## Mutations

### `POST /api/mutations/generate`

MVP stub endpoint. It must return a valid schema with an empty list or 1-2 fixed example mutations to wire up the frontend.

Request:

```json
{
  "scenario_ids": ["sc_create_card_001"],
  "mutation_types": ["data", "flow", "expectation_inversion"],
  "max_per_scenario": 3
}
```

Field defaults:

- `mutation_types` is optional; defaults to all three types.
- `max_per_scenario` is optional; defaults to `3`.

Response:

```json
{
  "mutations": []
}
```

Each item in `mutations` follows `MutatedScenario` in `docs/SCHEMAS.md`.

## Reports

### `GET /api/reports/{report_id}`

Returns report metadata and links to `report.json` and `report.html`.

## System

### `GET /health`

Liveness probe. Returns `{"status": "ok"}`. Exposed from Milestone 0.

### `GET /api/settings`

Returns runtime settings for the frontend settings drawer. Secret values are never returned; only `configured` booleans are exposed.

Response:

```json
{
  "models": {
    "text_llm_provider": "openai_compatible",
    "openai_compatible_provider_name": "Codex API",
    "openai_compatible_home_url": "https://openai.com",
    "openai_compatible_base_url": "https://api.openai.com/v1",
    "openai_compatible_model": "gpt-5.5",
    "openai_compatible_note": "",
    "openai_compatible_api_key_configured": true,
    "deepseek_model": "deepseek-v4-pro",
    "deepseek_api_key_configured": false,
    "browser_use_model": "bu-latest",
    "browser_use_api_key_configured": false,
    "browser_use_llm_fallback_enabled": false,
    "browser_use_cloud_browser_enabled": false,
    "glm_vision_model": "glm-4.6v",
    "glm_api_key_configured": true
  }
}
```

### `PATCH /api/settings`

Updates runtime settings and persists model-related fields to repository root `.env`. Secret fields are write-only; an empty API key does not overwrite an existing key. The MVP must reject `browser_use_cloud_browser_enabled=true`.

Request:

```json
{
  "models": {
    "text_llm_provider": "openai_compatible",
    "openai_compatible_provider_name": "Clauddy",
    "openai_compatible_home_url": "https://clauddy.com",
    "openai_compatible_base_url": "https://clauddy.com/v1",
    "openai_compatible_api_key": "write-only-new-key",
    "openai_compatible_model": "gpt-5.5",
    "openai_compatible_note": "公司专用账号",
    "browser_use_cloud_browser_enabled": false,
    "glm_vision_model": "glm-4.6v",
    "glm_api_key": null
  }
}
```

Response returns the same shape as `GET /api/settings`, with no secret values.

### `GET /api/doctor`

Environment readiness check used by the frontend settings drawer. Verifies OpenAI-compatible text model settings, legacy provider keys, GLM vision key, browser-use installation, database, ChromaDB, and artifact root.

Response:

```json
{
  "status": "ok",
  "checks": {
    "text_llm_provider": {"status": "ok", "detail": "openai_compatible"},
    "openai_compatible_api": {"status": "ok", "detail": "key configured for Codex API / gpt-5.5"},
    "deepseek_api": {"status": "warning", "detail": "not selected"},
    "browser_use_llm": {"status": "warning", "detail": "not selected"},
    "browser_use_cloud_browser": {"status": "ok", "detail": "disabled for MVP"},
    "glm_vision_api": {"status": "ok", "detail": "key configured"},
    "browser_use": {"status": "ok", "detail": "browser-use 0.12.x installed"},
    "database": {"status": "ok", "detail": "sqlite reachable"},
    "chroma": {"status": "ok", "detail": "persist dir writable"},
    "artifact_root": {"status": "ok", "detail": "data/runs writable"}
  }
}
```

Each check status is `ok`, `warning`, or `error`. Top-level `status` is the worst child status.
