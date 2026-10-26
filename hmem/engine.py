"""H-MEM engine facade for VeriForge.

Composes store, retrieval, ledger, conflict detection into one service
boundary. Exposes store/search/retrieve/invalidate with audit trail and
feedback loop (spec §9.2 deltas).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from hmem.conflicts import ConflictDetectionService
from hmem.ledger import TrustLedger
from hmem.models import (
    FEEDBACK_DELTAS,
    Entity,
    Memory,
    MemoryLayer,
    MemoryType,
    Provenance,
    ProvenanceOrigin,
    RetrievalResult,
    TrustAction,
    clamp01,
)
from hmem.retrieval import MemoryRetrievalService
from hmem.store import MemoryStore

logger = logging.getLogger("veriforge.hmem.engine")

DEFAULT_DATA_DIR = Path(os.getenv("HMEM_DATA_DIR", "./.hmem"))


class HMemEngine:
    """Single-process H-MEM engine. Thread-safe via store/ledger locks."""

    def __init__(self, data_dir: Path | None = None, actor: str = "veriforge"):
        data_dir = data_dir or DEFAULT_DATA_DIR
        self.actor = actor
        self.store = MemoryStore(data_dir / "memories.json")
        self.ledger = TrustLedger(data_dir / "trust-ledger.jsonl")
        self.retrieval = MemoryRetrievalService(self.store)
        self.conflicts = ConflictDetectionService(self.store)

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    def remember(
        self,
        content: str,
        *,
        tenant_id: str,
        investigation_id: str | None = None,
        type: MemoryType = MemoryType.FACTUAL,
        layer: MemoryLayer = MemoryLayer.WORKING,
        source: str,
        provenance_label: str,
        provenance_origin: ProvenanceOrigin = ProvenanceOrigin.INVESTIGATION,
        provenance_refs: tuple[str, ...] = (),
        confidence: float = 1.0,
        tags: tuple[str, ...] = (),
        domain: str | None = None,
        entities: tuple[Entity, ...] = (),
        related_to: tuple[str, ...] = (),
        supersedes: str | None = None,
    ) -> Memory:
        memory = Memory(
            content=content,
            type=type,
            layer=layer,
            source=source,
            provenance=Provenance(
                origin=provenance_origin,
                learned_at=datetime.now(timezone.utc),
                label=provenance_label,
                refs=provenance_refs,
            ),
            confidence=confidence,
            tags=tags,
            domain=domain,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            entities=entities,
            related_to=related_to,
            supersedes=supersedes,
        )
        self.store.add(memory)
        self.ledger.record(memory.id, TrustAction.CREATE, self.actor, new_state=memory.to_dict())
        return memory

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def recall(
        self,
        query: str,
        *,
        tenant_id: str,
        investigation_id: str | None = None,
        top_n: int = 5,
        strategy: str = "comprehensive",
        include_related_investigations: bool = True,
    ) -> RetrievalResult:
        """Recall memories for a scope.

        include_related_investigations=True (default) surfaces matching
        memories recorded under other investigation ids of the SAME tenant —
        the intended cross-investigation correlation path, with attribution
        preserved on each trace. Tenant boundaries are never crossed.
        """
        result = self.retrieval.retrieve(
            query,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            top_n=top_n,
            strategy=strategy,
            include_related=include_related_investigations,
        )
        for memory in result.memories:
            self.ledger.record(memory.id, TrustAction.READ, self.actor, details={"query": query[:200]})
        return result

    # ------------------------------------------------------------------
    # Invalidate
    # ------------------------------------------------------------------

    def invalidate(self, memory_id: str) -> bool:
        memory = self.store.get(memory_id)
        if not memory:
            return False
        previous = memory.to_dict()
        removed = self.store.invalidate(memory_id)
        if removed:
            self.ledger.record(memory_id, TrustAction.DELETE, self.actor, previous_state=previous)
        return removed

    # ------------------------------------------------------------------
    # Feedback (spec §9.2 exact deltas)
    # ------------------------------------------------------------------

    def feedback(self, memory_id: str, kind: str) -> Memory | None:
        if kind not in FEEDBACK_DELTAS:
            raise ValueError(f"Unknown feedback kind: {kind}")
        memory = self.store.get(memory_id)
        if not memory:
            return None
        previous = memory.to_dict()
        if kind == "helpful":
            memory.access_count += 1
        memory.confidence = clamp01(memory.confidence + FEEDBACK_DELTAS[kind])
        if kind == "wrong" and "review" not in memory.tags:
            memory.tags = memory.tags + ("review",)
        self.store.update(memory)
        self.ledger.record(
            memory_id,
            TrustAction.FEEDBACK,
            self.actor,
            previous_state=previous,
            new_state=memory.to_dict(),
            details={"kind": kind, "delta": FEEDBACK_DELTAS[kind]},
        )
        return memory

    # ------------------------------------------------------------------
    # Conflicts
    # ------------------------------------------------------------------

    def scan_conflicts(self, *, tenant_id: str, investigation_id: str | None = None):
        found = self.conflicts.scan(tenant_id, investigation_id)
        for conflict in found:
            self.ledger.record(
                conflict.memory_a,
                TrustAction.CONFLICT_DETECTED,
                self.actor,
                details={
                    "conflict_id": conflict.conflict_id,
                    "other_memory": conflict.memory_b,
                    "reason": conflict.reason,
                    "confidence": conflict.confidence,
                },
            )
        return found

    # ------------------------------------------------------------------
    # Health — truthful status (spec: safe failure)
    # ------------------------------------------------------------------

    def health(self) -> dict[str, object]:
        try:
            counts = self.store.count()
            return {
                "status": "available",
                "memories": counts,
                "ledger_entries": self.ledger.count(),
                "pending_conflicts": len(self.conflicts.pending()),
                "dreaming": "not_implemented",
                "sleep_cycle": "not_implemented",
            }
        except Exception as exc:  # noqa: BLE001 — health must never raise
            logger.exception("H-MEM health check failed")
            return {"status": "failed", "error": str(exc)}


_engine: HMemEngine | None = None
_engine_data_dir: Path | None = None


def get_hmem_engine() -> HMemEngine:
    """Return the shared engine, re-initializing if HMEM_DATA_DIR changed."""
    global _engine, _engine_data_dir
    current_dir = Path(os.getenv("HMEM_DATA_DIR", "./.hmem"))
    if _engine is None or _engine_data_dir != current_dir:
        _engine = HMemEngine(data_dir=current_dir)
        _engine_data_dir = current_dir
    return _engine


def reset_hmem_engine() -> None:
    global _engine, _engine_data_dir
    _engine = None
    _engine_data_dir = None
