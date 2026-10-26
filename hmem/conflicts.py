"""Conflict detection and resolution (spec §10).

Detection heuristics: opposing phrase pairs, same-entity divergent claims.
supersedes relation suppresses conflict (intended replacement).
Auto-resolve only at decision confidence >= 0.70; everything else queued
as pending proposals. Losing record marked supersededBy, never deleted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from hmem.models import AUTO_RESOLVE_GATE, Conflict, Memory
from hmem.store import MemoryStore

logger = logging.getLogger("veriforge.hmem.conflicts")

OPPOSING_PAIRS: tuple[tuple[str, str], ...] = (
    ("always", "never"),
    ("enable", "disable"),
    ("enabled", "disabled"),
    ("safe", "malicious"),
    ("safe", "phishing"),
    ("legitimate", "fraudulent"),
    ("legitimate", "malicious"),
    ("trusted", "suspicious"),
    ("verified", "unverified"),
    ("allow", "block"),
    ("is", "is not"),
)


class ConflictDetectionService:
    def __init__(self, store: MemoryStore):
        self._store = store
        self._conflicts: dict[str, Conflict] = {}

    def _contradicts(self, a: Memory, b: Memory) -> tuple[bool, str, float]:
        if a.id == b.id:
            return False, "", 0.0
        # supersedes relation suppresses conflict (spec §10.1)
        if a.supersedes == b.id or b.supersedes == a.id or a.superseded_by or b.superseded_by:
            return False, "", 0.0
        text_a, text_b = a.content.casefold(), b.content.casefold()
        confidence = 0.0
        reasons: list[str] = []
        for left, right in OPPOSING_PAIRS:
            if (left in text_a and right in text_b) or (right in text_a and left in text_b):
                confidence += 0.5
                reasons.append(f"opposing phrases '{left}'/'{right}'")
                break
        # Shared entities increase confidence (spec §10.1)
        entities_a = {e.name.casefold() for e in a.entities}
        entities_b = {e.name.casefold() for e in b.entities}
        shared = entities_a & entities_b
        if shared and reasons:
            confidence += 0.2
            reasons.append(f"shared entities: {sorted(shared)}")
        if a.domain and a.domain == b.domain and reasons:
            confidence += 0.1
        # Explicit relation lowers false positives
        if b.id in a.related_to or a.id in b.related_to:
            confidence -= 0.2
        return (confidence >= 0.5 and bool(reasons)), "; ".join(reasons), min(1.0, confidence)

    def scan(self, tenant_id: str, investigation_id: str | None = None) -> list[Conflict]:
        memories = self._store.all_for_scope(tenant_id, investigation_id)
        found: list[Conflict] = []
        for i, a in enumerate(memories):
            for b in memories[i + 1 :]:
                is_conflict, reason, confidence = self._contradicts(a, b)
                if is_conflict:
                    conflict = Conflict(
                        memory_a=a.id,
                        memory_b=b.id,
                        reason=reason,
                        confidence=confidence,
                        detected_at=datetime.now(timezone.utc),
                    )
                    self._conflicts[conflict.conflict_id] = conflict
                    found.append(conflict)
        return found

    def resolve(self, conflict_id: str, resolution: str, loser_id: str | None, winner_id: str | None) -> Conflict | None:
        """Apply a resolution. Caller records the ledger entry.

        Auto-resolution callers must check decision confidence >= 0.70 first.
        """
        conflict = self._conflicts.get(conflict_id)
        if not conflict or conflict.resolved:
            return conflict
        object.__setattr__(conflict, "resolved", True)
        object.__setattr__(conflict, "resolution", resolution)
        if loser_id and winner_id:
            loser = self._store.get(loser_id)
            if loser:
                loser.superseded_by = winner_id
                self._store.update(loser)
        return conflict

    def decision_confidence(self, a: Memory, b: Memory) -> float:
        """Weighted auto-decision heuristic (spec §10.2)."""
        score = 0.0
        if a.confidence != b.confidence:
            score += 0.3
        if a.access_count != b.access_count:
            score += 0.2
        if a.timestamp != b.timestamp:
            score += 0.2
        if "user_correction" in (a.source, b.source):
            score += 0.3  # user_correction = high source reliability
        return min(1.0, score)

    def pending(self) -> list[Conflict]:
        return [c for c in self._conflicts.values() if not c.resolved]

    @property
    def auto_resolve_gate(self) -> float:
        return AUTO_RESOLVE_GATE
