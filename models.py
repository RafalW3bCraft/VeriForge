from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

InputType = Literal["message", "email", "url", "image"]
Verdict = Literal["SAFE", "LOW", "SUSPICIOUS", "HIGH", "CRITICAL"]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=30000)
    input_type: InputType = "message"
    context: dict[str, Any] = Field(default_factory=dict)


class Claim(BaseModel):
    id: str
    kind: str
    value: str
    source: str = "message"
    snippet: str | None = Field(default=None, max_length=240)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Evidence(BaseModel):
    id: str
    kind: str
    value: str
    source: str = "message"
    snippet: str | None = Field(default=None, max_length=240)
    observed: bool = True


class ExtractionResult(BaseModel):
    urls: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    urgency_terms: list[str] = Field(default_factory=list)
    credential_terms: list[str] = Field(default_factory=list)
    financial_terms: list[str] = Field(default_factory=list)
    requests_credentials: bool = False
    requests_financial_action: bool = False
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class Finding(BaseModel):
    finding: str
    severity: Literal["low", "medium", "high", "critical"]
    evidence: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)


class AgentResult(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    critical_signal: float = Field(default=0.0, ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    findings: list[Finding] = Field(default_factory=list)


class VerificationResult(AgentResult):
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    evidence_strength: float = Field(default=0.0, ge=0.0, le=1.0)


class AgentResults(BaseModel):
    identity: AgentResult
    infrastructure: AgentResult
    social_engineering: AgentResult
    verification: VerificationResult


class RiskDecision(BaseModel):
    risk_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_strength: float = Field(ge=0.0, le=1.0)
    verdict: Verdict
    recommended_action: str


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str = "workflow"
    evidence_id: str | None = None


class EvidenceGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class NormalizedEmail(BaseModel):
    message_id: str
    sender: str
    recipient: str | None = None
    subject: str = ""
    body: str = Field(min_length=1, max_length=30000)
    received_at: datetime | None = None
    urls: list[str] = Field(default_factory=list)


class WebhookEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(alias="id", min_length=1, max_length=100)
    event_type: str = Field(alias="type", min_length=1, max_length=80)
    created_at: datetime | None = None
    data: dict[str, Any]


class WebhookAcknowledgement(BaseModel):
    status: Literal["accepted", "duplicate", "skipped"]
    event_id: str
    message_id: str | None = None


class AnalysisResponse(BaseModel):
    analysis_id: str
    created_at: datetime
    input_type: InputType
    score: float = Field(ge=0.0, le=100.0)
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    risk_decision: RiskDecision
    summary: str
    recommended_action: str
    extraction: ExtractionResult
    findings: list[Finding]
    agents: AgentResults
    graph: EvidenceGraph
    meta: dict[str, Any] = Field(default_factory=dict)


class AnalysisSummary(BaseModel):
    analysis_id: str
    created_at: datetime
    input_type: InputType
    score: float
    verdict: Verdict
    summary: str


class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummary]