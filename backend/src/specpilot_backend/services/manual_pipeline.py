from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, Field

from specpilot_backend.agent.browser_use_runner import create_browser_use_llm
from specpilot_backend.config import Settings, get_settings
from specpilot_backend.generation.validators import (
    validate_feature_payload,
    validate_scenario_payload,
)
from specpilot_backend.ingestion.chunker import ManualChunk, chunk_markdown
from specpilot_backend.ingestion.crawler import (
    CrawlScope,
    CrawledManualPage,
    crawl_manual_pages,
)
from specpilot_backend.ingestion.indexer import index_chunks
from specpilot_backend.prompts.templates import (
    build_feature_extraction_prompt,
    build_scenario_generation_prompt,
)
from specpilot_backend.services import persistence

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ManualPipelineRequest:
    base_url: str = "https://docs.4gaboards.com/"
    sections: tuple[str, ...] = ("user-manual", "admin-manual")
    language: str = "en"
    max_pages: int = 250
    max_scenarios_per_feature: int = 3
    start_stage: Literal["crawl", "index", "features", "scenarios"] = "crawl"
    resume_from_job_id: str | None = None
    crawl_id: str | None = None
    index_id: str | None = None
    feature_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrawlOutput:
    crawl_id: str
    pages: list[CrawledManualPage]
    chunks: list[ManualChunk]


class _FeatureItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    feature_id: str
    module: str
    title: str
    summary: str
    source_urls: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = 0.75
    coverage_status: str = "covered"


class _FeatureOutput(BaseModel):
    features: list[_FeatureItem] = Field(default_factory=list)


class _ScenarioItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scenario_id: str
    feature_id: str
    title: str
    priority: str
    difficulty: str
    source_urls: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    test_data: dict[str, object] = Field(default_factory=dict)
    steps: list[dict[str, object]] = Field(default_factory=list)
    expectations: list[dict[str, object]] = Field(default_factory=list)
    max_steps: int = 20
    requires_visual_check: bool = False
    review_status: str = "auto_validated"
    is_mutation: bool = False
    data_dependency: str = "none"
    fixtures: list[dict[str, object]] = Field(default_factory=list)


class _ScenarioOutput(BaseModel):
    scenarios: list[_ScenarioItem] = Field(default_factory=list)


def run_manual_pipeline(
    job_id: str,
    request: ManualPipelineRequest | None = None,
    *,
    settings: Settings | None = None,
) -> None:
    resolved_request = request or ManualPipelineRequest()
    resolved_settings = settings or get_settings()
    result: dict[str, object] = {"warnings": []}
    warnings: list[dict[str, object]] = []
    try:
        result = _resume_result(resolved_request.resume_from_job_id)
        warnings = _warnings_from_result(result)
        persistence.update_job_record(
            job_id,
            status="running",
            stage=resolved_request.start_stage,
            progress=_stage_progress(resolved_request.start_stage),
            message=_stage_message(resolved_request.start_stage),
            result=result,
        )

        chunks: list[ManualChunk] = []
        features: list[dict[str, object]] = []

        if resolved_request.start_stage == "crawl":
            crawl_output = crawl_manual_chunks(resolved_request)
            chunks = crawl_output.chunks
            result.update(
                {
                    "crawl_id": crawl_output.crawl_id,
                    "pages_count": len(crawl_output.pages),
                    "chunks_count": len(crawl_output.chunks),
                    "pages": _page_summaries(crawl_output.pages),
                    "warnings": warnings,
                    "zero_locator": True,
                    "replaced_existing": False,
                }
            )
            _update_pipeline_job(
                job_id,
                stage="index",
                progress=35,
                message="正在切块并写入 ChromaDB",
                result=result,
            )
            index_id = index_manual_chunks(chunks, crawl_output.crawl_id)
            result["index_id"] = index_id
        elif resolved_request.start_stage == "index":
            crawl_id = _resolve_input_id(
                "crawl_id",
                explicit=resolved_request.crawl_id,
                result=result,
            )
            chunks = load_chunks_manifest(crawl_id, manifest_type="crawls")
            result.update(
                {
                    "crawl_id": crawl_id,
                    "chunks_count": len(chunks),
                    "warnings": warnings,
                    "zero_locator": True,
                    "replaced_existing": False,
                }
            )
            _update_pipeline_job(
                job_id,
                stage="index",
                progress=35,
                message="正在切块并写入 ChromaDB",
                result=result,
            )
            result["index_id"] = index_manual_chunks(chunks, crawl_id)
        else:
            index_id = _resolve_input_id(
                "index_id",
                explicit=resolved_request.index_id,
                result=result,
                required=resolved_request.start_stage == "features",
            )
            if index_id:
                chunks = _load_chunks_manifest_if_exists(index_id, manifest_type="indexes")
                result["index_id"] = index_id

        if resolved_request.start_stage in {"crawl", "index", "features"}:
            if not chunks:
                index_id = _resolve_input_id(
                    "index_id",
                    explicit=resolved_request.index_id,
                    result=result,
                )
                chunks = load_chunks_manifest(index_id, manifest_type="indexes")
            _update_pipeline_job(
                job_id,
                stage="features",
                progress=60,
                message="正在基于手册证据提取功能点",
                result=result,
            )
            features = _extract_features_with_optional_warnings(
                chunks,
                resolved_settings,
                warnings=warnings,
            )
            result.update(
                {
                    "features": features,
                    "features_count": len(features),
                    "warnings": warnings,
                }
            )
        else:
            features = _resolve_scenario_features(
                result,
                feature_ids=resolved_request.feature_ids,
            )
            if not chunks:
                chunks = _feature_chunks_from_features(features)
            result.update(
                {
                    "features": features,
                    "features_count": len(features),
                    "warnings": warnings,
                    "zero_locator": True,
                    "replaced_existing": False,
                }
            )

        _update_pipeline_job(
            job_id,
            stage="scenarios",
            progress=82,
            message="正在生成零 locator 测试场景",
            result=result,
        )
        scenarios = generate_scenarios_from_features(
            features,
            chunks,
            resolved_settings,
            max_scenarios_per_feature=resolved_request.max_scenarios_per_feature,
            warnings=warnings,
        )
        if not features or not scenarios:
            if not scenarios:
                raise RuntimeError("无有效场景生成")
            raise RuntimeError("No valid features were generated.")

        if resolved_request.start_stage != "scenarios":
            persistence.clear_feature_payloads()
            for feature in features:
                persistence.save_feature_payload(feature)
        persistence.clear_non_mutation_scenario_payloads()
        for scenario in scenarios:
            persistence.save_scenario_payload(scenario)

        result.update(
            {
                "features": features,
                "warnings": warnings,
                "features_count": len(features),
                "scenarios_count": len(scenarios),
                "zero_locator": True,
                "replaced_existing": True,
            }
        )
        persistence.update_job_record(
            job_id,
            status="succeeded",
            stage="done",
            progress=100,
            message="真实手册生成完成",
            result=result,
        )
    except Exception as exc:
        LOGGER.exception("Manual pipeline job %s failed", job_id)
        persistence.update_job_record(
            job_id,
            status="failed",
            progress=0,
            message="真实手册生成失败，已保留原有数据",
            error=_exception_summary(exc),
        )


def crawl_manual_chunks(request: ManualPipelineRequest) -> CrawlOutput:
    from specpilot_backend.ids import new_id

    crawl_id = new_id("crawl")
    scope = CrawlScope(
        base_url=request.base_url,
        sections=tuple(request.sections),
        language=request.language,
    )
    start_urls = [
        urljoin(request.base_url, f"/docs/{section}") for section in request.sections
    ]
    pages = asyncio.run(
        crawl_manual_pages(start_urls, scope=scope, max_pages=request.max_pages)
    )
    chunks: list[ManualChunk] = []
    for page in pages:
        chunks.extend(
            chunk_markdown(
                page.markdown,
                page_url=page.url,
                page_title=page.title,
                manual_section=page.manual_section,
                module=page.module,
                module_variant=page.module_variant,
                language=page.language,
            )
        )
    _write_pages_manifest(crawl_id, pages)
    _write_chunks_manifest(crawl_id, chunks, manifest_type="crawls")
    return CrawlOutput(crawl_id=crawl_id, pages=pages, chunks=chunks)


def index_manual_chunks(chunks: list[ManualChunk], crawl_id: str) -> str:
    from specpilot_backend.ids import new_id

    index_id = new_id("idx")
    index_chunks(chunks)
    _write_chunks_manifest(index_id, chunks, manifest_type="indexes")
    return index_id


def extract_features_from_chunks(
    chunks: list[ManualChunk],
    settings: Settings,
    *,
    warnings: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    operational_chunks = [
        chunk for chunk in chunks if chunk.metadata.get("is_ui_operational") is not False
    ]
    grouped: dict[str, list[ManualChunk]] = defaultdict(list)
    for chunk in operational_chunks:
        grouped[str(chunk.metadata.get("module", "Other"))].append(chunk)

    features: list[dict[str, object]] = []
    for module_chunks in grouped.values():
        prompt = build_feature_extraction_prompt(
            _chunk_prompt_payload(chunk) for chunk in module_chunks
        )
        try:
            output = _invoke_structured_model(prompt, _FeatureOutput, settings)
        except Exception as exc:
            _append_warning(
                warnings,
                stage="features",
                scope=str(module_chunks[0].metadata.get("module", "Other")),
                message=_exception_summary(exc),
            )
            LOGGER.warning(
                "Skipping feature extraction group %s after model error: %s",
                module_chunks[0].metadata.get("module", "Other"),
                _exception_summary(exc),
            )
            continue
        for item in output.features:
            payload = item.model_dump()
            try:
                validate_feature_payload(payload, module_chunks)
            except Exception as exc:
                _append_warning(
                    warnings,
                    stage="features",
                    scope=str(payload.get("feature_id", "<unknown>")),
                    message=_exception_summary(exc),
                )
                LOGGER.warning(
                    "Skipping invalid feature %s: %s",
                    payload.get("feature_id", "<unknown>"),
                    _exception_summary(exc),
                )
                continue
            features.append(payload)
    return _dedupe_by_id(features, "feature_id")


def generate_scenarios_from_features(
    features: list[dict[str, object]],
    chunks: list[ManualChunk],
    settings: Settings,
    *,
    max_scenarios_per_feature: int = 3,
    warnings: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = []
    for feature in features:
        feature_id = str(feature.get("feature_id", "<unknown>"))
        evidence_chunks = _evidence_chunks_for_feature(feature, chunks)
        if not evidence_chunks:
            _append_warning(
                warnings,
                stage="scenarios",
                scope=feature_id,
                message="No evidence chunks matched feature.",
            )
            continue
        prompt = build_scenario_generation_prompt(
            feature=feature,
            evidence_chunks=(_chunk_prompt_payload(chunk) for chunk in evidence_chunks),
        )
        try:
            output = _invoke_structured_model(prompt, _ScenarioOutput, settings)
        except Exception as exc:
            _append_warning(
                warnings,
                stage="scenarios",
                scope=feature_id,
                message=_exception_summary(exc),
            )
            LOGGER.warning(
                "Skipping scenario generation for feature %s after model error: %s",
                feature_id,
                _exception_summary(exc),
            )
            continue
        for item in output.scenarios[:max_scenarios_per_feature]:
            payload = item.model_dump()
            payload["feature_id"] = feature_id
            payload["is_mutation"] = False
            try:
                validate_scenario_payload(payload, evidence_chunks)
            except Exception as exc:
                _append_warning(
                    warnings,
                    stage="scenarios",
                    scope=str(payload.get("scenario_id", feature_id)),
                    message=_exception_summary(exc),
                )
                LOGGER.warning(
                    "Skipping invalid scenario %s: %s",
                    payload.get("scenario_id", "<unknown>"),
                    _exception_summary(exc),
                )
                continue
            scenarios.append(payload)
    return _dedupe_by_id(scenarios, "scenario_id")


def load_chunks_manifest(manifest_id: str, *, manifest_type: str) -> list[ManualChunk]:
    path = _data_root() / manifest_type / manifest_id / "chunks.jsonl"
    chunks: list[ManualChunk] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        chunks.append(ManualChunk(content=item["content"], metadata=item["metadata"]))
    return chunks


def _load_chunks_manifest_if_exists(
    manifest_id: str,
    *,
    manifest_type: str,
) -> list[ManualChunk]:
    path = _data_root() / manifest_type / manifest_id / "chunks.jsonl"
    if not path.exists():
        return []
    return load_chunks_manifest(manifest_id, manifest_type=manifest_type)


def _extract_features_with_optional_warnings(
    chunks: list[ManualChunk],
    settings: Settings,
    *,
    warnings: list[dict[str, object]],
) -> list[dict[str, object]]:
    parameters = inspect.signature(extract_features_from_chunks).parameters
    if "warnings" not in parameters:
        return extract_features_from_chunks(chunks, settings)
    return extract_features_from_chunks(chunks, settings, warnings=warnings)


def _invoke_structured_model(
    prompt: str,
    output_model: type[_FeatureOutput] | type[_ScenarioOutput],
    settings: Settings,
) -> Any:
    from browser_use.llm.messages import UserMessage

    async def call_model() -> Any:
        llm = create_browser_use_llm(settings)
        result = await llm.ainvoke([UserMessage(content=prompt)], output_format=output_model)
        return result.completion

    return asyncio.run(call_model())


def _evidence_chunks_for_feature(
    feature: dict[str, object],
    chunks: list[ManualChunk],
) -> list[ManualChunk]:
    urls = set(_string_list(feature.get("source_urls")))
    quotes = _string_list(feature.get("evidence_quotes"))
    matched = [
        chunk
        for chunk in chunks
        if str(chunk.metadata.get("source_url")) in urls
        or any(quote in chunk.content for quote in quotes)
    ]
    return matched or [
        chunk
        for chunk in chunks
        if chunk.metadata.get("module") == feature.get("module")
    ]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _chunk_prompt_payload(chunk: ManualChunk) -> dict[str, object]:
    return {
        "content": chunk.content,
        "metadata": {
            "source_url": chunk.metadata.get("source_url"),
            "page_title": chunk.metadata.get("page_title"),
            "heading_path": chunk.metadata.get("heading_path"),
            "module": chunk.metadata.get("module"),
            "manual_section": chunk.metadata.get("manual_section"),
            "language": chunk.metadata.get("language"),
        },
    }


def _dedupe_by_id(
    payloads: Iterable[dict[str, object]],
    id_field: str,
) -> list[dict[str, object]]:
    deduped: dict[str, dict[str, object]] = {}
    for payload in payloads:
        deduped[str(payload[id_field])] = payload
    return list(deduped.values())


def _resume_result(resume_from_job_id: str | None) -> dict[str, object]:
    if not resume_from_job_id:
        return {"warnings": []}
    payload = persistence.get_job_payload(resume_from_job_id)
    if payload is None:
        raise ValueError(f"resume_from_job_id not found: {resume_from_job_id}")
    result = payload.get("result")
    if not isinstance(result, dict):
        return {"warnings": []}
    return dict(result)


def _warnings_from_result(result: dict[str, object]) -> list[dict[str, object]]:
    warnings = result.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [item for item in warnings if isinstance(item, dict)]


def _append_warning(
    warnings: list[dict[str, object]] | None,
    *,
    stage: str,
    scope: str,
    message: str,
) -> None:
    if warnings is None:
        return
    warnings.append({"stage": stage, "scope": scope, "message": message})


def _page_summaries(pages: list[CrawledManualPage]) -> list[dict[str, object]]:
    return [
        {
            "title": page.title,
            "url": page.url,
            "manual_section": page.manual_section,
            "module": page.module,
        }
        for page in pages
    ]


def _resolve_input_id(
    field_name: str,
    *,
    explicit: str | None,
    result: dict[str, object],
    required: bool = True,
) -> str:
    value = explicit or result.get(field_name)
    if isinstance(value, str) and value:
        return value
    if not required:
        return ""
    raise ValueError(f"{field_name} is required for this pipeline stage.")


def _resolve_scenario_features(
    result: dict[str, object],
    *,
    feature_ids: tuple[str, ...],
) -> list[dict[str, object]]:
    result_features = result.get("features")
    if isinstance(result_features, list) and result_features:
        features = [item for item in result_features if isinstance(item, dict)]
    else:
        features = persistence.list_feature_payloads()
    if feature_ids:
        wanted = set(feature_ids)
        features = [
            feature
            for feature in features
            if str(feature.get("feature_id")) in wanted
        ]
    if not features:
        raise ValueError("No features available for scenario generation.")
    return features


def _feature_chunks_from_features(
    features: list[dict[str, object]],
) -> list[ManualChunk]:
    chunks: list[ManualChunk] = []
    for feature in features:
        urls = _string_list(feature.get("source_urls"))
        quotes = _string_list(feature.get("evidence_quotes"))
        content = "\n".join(quotes) or str(feature.get("summary", ""))
        for url in urls or ["manual-pipeline:feature"]:
            chunks.append(
                ManualChunk(
                    content=content,
                    metadata={
                        "source_url": url,
                        "page_url": url,
                        "page_title": feature.get("title", ""),
                        "heading_path": feature.get("title", ""),
                        "module": feature.get("module", "Other"),
                        "manual_section": "unknown",
                        "language": "en",
                        "is_ui_operational": True,
                    },
                )
            )
    return chunks


def _update_pipeline_job(
    job_id: str,
    *,
    stage: str,
    progress: int,
    message: str,
    result: dict[str, object],
) -> None:
    persistence.update_job_record(
        job_id,
        stage=stage,
        progress=progress,
        message=message,
        result=result,
    )


def _stage_progress(stage: str) -> int:
    return {"crawl": 5, "index": 35, "features": 60, "scenarios": 82}[stage]


def _stage_message(stage: str) -> str:
    return {
        "crawl": "正在抓取 4ga Boards 英文 user/admin manual",
        "index": "正在复用抓取结果并索引证据",
        "features": "正在复用索引并提取功能点",
        "scenarios": "正在复用功能点并生成测试场景",
    }[stage]


def _exception_summary(exc: BaseException) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _write_pages_manifest(crawl_id: str, pages: list[CrawledManualPage]) -> None:
    path = _data_root() / "crawls" / crawl_id / "pages.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(page.__dict__, ensure_ascii=False) for page in pages),
        encoding="utf-8",
    )


def _write_chunks_manifest(
    manifest_id: str,
    chunks: list[ManualChunk],
    *,
    manifest_type: str,
) -> None:
    path = _data_root() / manifest_type / manifest_id / "chunks.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {"content": chunk.content, "metadata": chunk.metadata},
            ensure_ascii=False,
        )
        for chunk in chunks
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _data_root() -> Path:
    return get_settings().artifact_root.parent
