# SpecPilot Requirements Baseline

This document normalizes `项目需求.md` into implementation requirements. It does not replace the original file.

## Product Goal

Build a local full-stack tool that extracts business knowledge from the 4ga Boards manual, generates executable structured web test scenarios, executes those scenarios with an LLM web agent, and verifies whether the target application behaves correctly.

Target documentation:

- `https://docs.4gaboards.com/`
- Crawl only English user/admin manual pages.
- Exclude developer manual, API documentation, deployment documentation, and non-UI operational content.

Target application:

- `https://demo.4gaboards.com/`

## Task 1: Manual-Driven Scenario Generation

The system must:

- ingest 4ga Boards user/admin manual pages;
- extract main functional points from manual evidence;
- generate structured scenarios for each feature;
- preserve source URLs and evidence quotes;
- reject or flag scenarios without valid manual evidence;
- visualize feature points and generated scenarios.

Scenario shape:

```text
[
  [step]+
  [expectation]?
]+
```

Implementation interpretation:

- `step` is a natural-language user action intention.
- `expectation` is a structured oracle used to verify final state.
- Scenarios must not contain selectors, locators, xpaths, DOM ids, or runtime browser-use element indices.

## Task 2: Scenario-Driven Web Testing Agent

The system must:

- execute generated scenarios against 4ga Boards demo;
- use an LLM web agent to plan and perform browser interactions;
- use OpenAI-compatible / Codex API settings as the default text model path, with DeepSeek and Browser Use hosted LLM settings retained only as explicit compatibility paths;
- keep execution context and trace history;
- verify execution completeness and functional correctness;
- output pass/fail/needs_review;
- classify failures and explain the reason.

Required agent architecture elements:

- planning: delegated to browser-use internal agent loop for a single scenario;
- memory: scenario data, manual evidence, run trace, and prior node state;
- execution: browser-use browser interactions;
- verification: deterministic DOM/text/URL checks plus GLM-4.6V visual checks where required.

## Scoring-Oriented Requirements

The MVP must support:

- feature extraction from the manual;
- scenario generation for major functions;
- scenario format compliance;
- simple scenario execution;
- correctness verification;
- frontend visualization for features, scenarios, live runs, and run history.

Innovation-oriented capabilities:

- evidence-grounded generation to reduce hallucination;
- feature coverage and scenario coverage metrics;
- scenario difficulty labels;
- stable execution for simple and medium scenarios;
- failure categories for typical application errors;
- mutation testing interface and schemas, with full mutation algorithms deferred after MVP.

## Acceptance Targets

The MVP is considered complete when:

- at least 8 features are extracted;
- features cover Project, Board, List, Card, Views, and Settings where manual evidence exists;
- at least 16 valid zero-locator scenarios are generated;
- each generated scenario includes source URLs and evidence quotes;
- simple scenario pass rate is at least 80% in a configured local run;
- medium scenario pass rate is at least 60% in a configured local run;
- run trace, screenshots, verification result, failure class, and report are persisted;
- the frontend exposes dashboard, feature tree, scenario table, live run, run history, and run detail views.
