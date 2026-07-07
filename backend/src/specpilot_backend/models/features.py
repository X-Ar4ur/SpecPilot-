from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FeatureModule = Literal[
    "Project",
    "Board",
    "List",
    "Card",
    "Views",
    "Settings",
    "Admin",
    "Other",
]
CoverageStatus = Literal["uncovered", "covered", "partial"]


class Feature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str
    module: FeatureModule
    title: str
    summary: str
    source_urls: list[str] = Field(min_length=1)
    evidence_quotes: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    coverage_status: CoverageStatus

    @field_validator("source_urls", "evidence_quotes")
    @classmethod
    def reject_empty_strings(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            msg = "source URLs and evidence quotes must not contain blank values"
            raise ValueError(msg)
        return values

    def evidence_quotes_are_supported(self, source_chunks: list[str]) -> bool:
        return all(
            any(quote in source_chunk for source_chunk in source_chunks)
            for quote in self.evidence_quotes
        )
