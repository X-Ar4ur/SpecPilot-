# SpecPilot Claude Implementation Contract

Claude must follow the same implementation contract as Codex.

Read and obey `AGENTS.md` first. If Claude-specific behavior is needed, it must still preserve every non-negotiable architecture rule and strict prohibition in `AGENTS.md`.

Required read order:

1. `AGENTS.md`
2. `项目需求.md`
3. `PLANv2.md`
4. `docs/REQUIREMENTS.md`
5. `docs/SPEC.md`
6. `docs/API.md`
7. `docs/SCHEMAS.md`
8. `docs/TESTING.md`
9. `docs/PROMPTS.md`
10. `docs/IMPLEMENTATION_PLAN.md`

Claude must not infer missing architecture. If a missing decision would change the stack, schema, API, execution model, security model, or MVP scope, ask before implementing.

Model/provider rule: use DeepSeek V4 Pro (`deepseek-v4-pro`) via `langchain-deepseek` by default. Browser Use hosted LLM via `BROWSER_USE_API_KEY` is allowed only when explicitly selected as the text model provider or fallback; it must not imply Browser Use Cloud Browser, `use_cloud=True`, `@sandbox`, or `cdp_url`.
