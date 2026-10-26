"""Canonical H-MEM data model per AGENTS.md §2.

A record without `source` is rejected by construction (mandatory field).
Provenance is mandatory for new writes.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    PERSONAL = "personal"
    FACTUAL = "factual"
    PREFERENCE = "preference"
    GENERAL = "general"


class MemoryLayer(str, Enum):
    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"


class ProvenanceOrigin(str, Enum):
    CHAT_MESSAGE = "chat_message"
    USER_CORRECTION = "user_correction"
    FILE_SAVE = "file_save"
    FILE_OPEN = "file_open"
    FILE_EDIT = "file_edit"
    MODEL_RESPONSE = "model_response"
    PLAN_COMPLETION = "plan_completion"
    DIRECT_CAPTURE = "direct_capture"
    INVESTIGATION = "investigation"  # VeriForge extension: mined from an investigation
    SYNTHESIS = "synthesis"


class TrustAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    FEEDBACK = "feedback"
    PROMOTE = "promote"
    DEMOTE = "demote"
    MERGE = "merge"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    SLEEP_CONSOLIDATE = "sleep_consolidate"
    SLEEP_ARCHIVE = "sleep_archive"
    SLEEP_SYNTHESIZE = "sleep_synthesize"
    DREAM_PROPOSED = "dream_proposed"
    DREAM_APPROVED = "dream_approved"
    DREAM_REJECTED = "dream_rejected"
    RESTORE = "restore"


LAYER_WEIGHTS: dict[MemoryLayer, float] = {
    MemoryLayer.LONG_TERM: 1.0,
    MemoryLayer.WORKING: 0.8,
    MemoryLayer.SHORT_TERM: 0.6,
}

# Trust gate: memories below this confidence may not enter long_term
HIGH_TRUST_CONFIDENCE_FLOOR = 0.70
# Retrieval threshold on final score (after confidence multiplier), spec §13.
# 0.35 is tuned for embedding-backed stores; model-free token-overlap scoring
# systematically scores lower, so the fallback threshold is lower.
RETRIEVAL_THRESHOLD = 0.35
RETRIEVAL_THRESHOLD_FALLBACK = 0.10
RETRIEVAL_TOP_N = 5
ENTITY_CAP = 10
RELATED_CAP = 5
# Feedback deltas, spec §9.2
FEEDBACK_DELTAS = {"helpful": 0.05, "not_helpful": -0.03, "wrong": -0.20}
AUTO_RESOLVE_GATE = 0.70
RECENCY_TIME_CONSTANT_DAYS = 14.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class Provenance:
    origin: ProvenanceOrigin
    learned_at: datetime
    label: str  # human-readable "how I learned this"
    refs: tuple[str, ...] = ()  # e.g. analysis_id, record ids


@dataclass
class Entity:
    name: str
    entity_type: str  # domain, url, ip, hash, email, concept, technology, person


@dataclass
class Memory:
    """Canonical memory record. `source` and `provenance` are mandatory."""

    content: str
    type: MemoryType
    source: str  # mandatory — rejected by construction if empty
    provenance: Provenance
    layer: MemoryLayer = MemoryLayer.SHORT_TERM
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=_now)
    last_accessed: datetime = field(default_factory=_now)
    access_count: int = 0
    tags: tuple[str, ...] = ()
    domain: str | None = None
    namespace: str | None = None
    confidence: float = 1.0
    # Scoping: investigation = chatId equivalent; tenant = namespace partition
    investigation_id: str | None = None
    tenant_id: str = "default"
    entities: tuple[Entity, ...] = ()
    related_to: tuple[str, ...] = ()
    supersedes: str | None = None
    superseded_by: str | None = None
    derived_from: tuple[str, ...] = ()
    score: float = 0.0  # runtime retrieval score

    def __post_init__(self) -> None:
        if not self.source or not self.source.strip():
            raise ValueError("Memory.source is mandatory (H-MEM spec §2)")
        if not self.content or not self.content.strip():
            raise ValueError("Memory.content must be non-empty")
        if len(self.entities) > ENTITY_CAP:
            raise ValueError(f"Entity cap exceeded ({ENTITY_CAP})")
        if len(self.related_to) > RELATED_CAP:
            raise ValueError(f"Related links cap exceeded ({RELATED_CAP})")
        self.confidence = clamp01(self.confidence)

    @property
    def is_superseded(self) -> bool:
        return self.superseded_by is not None

    def recency_boost(self, now: datetime | None = None) -> float:
        now = now or _now()
        age_days = max(0.0, (now - self.last_accessed).total_seconds() / 86400.0)
        return math.exp(-age_days / RECENCY_TIME_CONSTANT_DAYS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type.value,
            "layer": self.layer.value,
            "timestamp": self.timestamp.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "tags": list(self.tags),
            "domain": self.domain,
            "namespace": self.namespace,
            "confidence": self.confidence,
            "source": self.source,
            "provenance": {
                "origin": self.provenance.origin.value,
                "learned_at": self.provenance.learned_at.isoformat(),
                "label": self.provenance.label,
                "refs": list(self.provenance.refs),
            },
            "investigation_id": self.investigation_id,
            "tenant_id": self.tenant_id,
            "entities": [{"name": e.name, "entity_type": e.entity_type} for e in self.entities],
            "related_to": list(self.related_to),
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "derived_from": list(self.derived_from),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        prov = data["provenance"]
        return cls(
            id=data["id"],
            content=data["content"],
            type=MemoryType(data["type"]),
            layer=MemoryLayer(data["layer"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            tags=tuple(data.get("tags", [])),
            domain=data.get("domain"),
            namespace=data.get("namespace"),
            confidence=data.get("confidence", 1.0),
            source=data["source"],
            provenance=Provenance(
                origin=ProvenanceOrigin(prov["origin"]),
                learned_at=datetime.fromisoformat(prov["learned_at"]),
                label=prov["label"],
                refs=tuple(prov.get("refs", [])),
            ),
            investigation_id=data.get("investigation_id"),
            tenant_id=data.get("tenant_id", "default"),
            entities=tuple(Entity(**e) for e in data.get("entities", [])),
            related_to=tuple(data.get("related_to", [])),
            supersedes=data.get("supersedes"),
            superseded_by=data.get("superseded_by"),
            derived_from=tuple(data.get("derived_from", [])),
        )


@dataclass(frozen=True)
class TrustLedgerEntry:
    memory_id: str
    action: TrustAction
    actor: str
    timestamp: datetime
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None
    details: dict[str, Any] = field(default_factory=dict)
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class Conflict:
    memory_a: str
    memory_b: str
    reason: str
    confidence: float
    detected_at: datetime
    conflict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resolved: bool = False
    resolution: str | None = None  # keep_a | keep_b | keep_both | merge | delete_both


@dataclass(frozen=True)
class RetrievalTrace:
    """Why a memory was selected (spec §6.2 trace metadata)."""

    memory_id: str
    relevance_score: float
    strategy: str  # minimal | personal | comprehensive
    retrieval_reason: str
    score_components: dict[str, float]


@dataclass(frozen=True)
class RetrievalResult:
    memories: tuple[Memory, ...]
    traces: tuple[RetrievalTrace, ...]
    query: str
    strategy: str
    retrieved_at: datetime
