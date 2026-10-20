from pydantic import BaseModel, Field
from typing import Literal

class CaseInfo(BaseModel):
    narrative: str
    symptoms: list[str] = Field(default_factory=list)
    duration: str | None = None
    age: int | None = None
    medications: list[str] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    urgent_signs: list[str] = Field(default_factory=list)

class ModelOpinion(BaseModel):
    provider: str
    content: str
    error: str | None = None

class EvidenceItem(BaseModel):
    pmid: str
    title: str
    abstract: str
    url: str
    publication: str = ""

class ConsultationResult(BaseModel):
    case: CaseInfo
    route: Literal["urgent", "simple", "collaborative"]
    questions: list[str]
    opinions: list[ModelOpinion]
    evidence: list[EvidenceItem]
    evidence_review: str
    disagreement_review: str
    report: str
    warnings: list[str] = Field(default_factory=list)
