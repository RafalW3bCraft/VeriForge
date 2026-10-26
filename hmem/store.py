"""Tiered memory store with per-investigation/per-tenant isolation.

Long-term and working tiers persist to a JSON file (durable enough for a
hackathon demo; SQLite backing via the main DB is a future enhancement).
Short-term is session-scoped in memory.

Isolation rule: retrieval is always scoped to (tenant_id, investigation_id).
No cross-tenant and no cross-investigation reads — a memory stored under
investigation A is never returned for investigation B unless explicitly
promoted to tenant-level shared knowledge (layer=long_term with
investigation_id=None), which requires the high-trust confidence floor.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from hmem.models import (
    HIGH_TRUST_CONFIDENCE_FLOOR,
    Memory,
    MemoryLayer,
)

logger = logging.getLogger("veriforge.hmem.store")


class MemoryStore:
    """Tiered persistence: short_term (volatile), working + long_term (durable)."""

    def __init__(self, persistence_path: Path | None = None):
        self._lock = RLock()
        self._short_term: dict[str, Memory] = {}
        self._working: dict[str, Memory] = {}
        self._long_term: dict[str, Memory] = {}
        self._persistence_path = persistence_path
        if persistence_path and persistence_path.exists():
            self._load(persistence_path)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self, path: Path) -> None:
        data = json.loads(path.read_text())
        for item in data.get("working", []):
            memory = Memory.from_dict(item)
            self._working[memory.id] = memory
        for item in data.get("long_term", []):
            memory = Memory.from_dict(item)
            self._long_term[memory.id] = memory
        logger.info("Loaded %d working + %d long-term memories", len(self._working), len(self._long_term))

    def _persist(self) -> None:
        if not self._persistence_path:
            return
        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "working": [m.to_dict() for m in self._working.values()],
            "long_term": [m.to_dict() for m in self._long_term.values()],
        }
        tmp = self._persistence_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self._persistence_path)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _tier(self, layer: MemoryLayer) -> dict[str, Memory]:
        return {
            MemoryLayer.SHORT_TERM: self._short_term,
            MemoryLayer.WORKING: self._working,
            MemoryLayer.LONG_TERM: self._long_term,
        }[layer]

    def add(self, memory: Memory) -> Memory:
        with self._lock:
            if memory.layer == MemoryLayer.LONG_TERM and memory.confidence < HIGH_TRUST_CONFIDENCE_FLOOR:
                raise ValueError(
                    f"Memory confidence {memory.confidence:.2f} below high-trust floor "
                    f"{HIGH_TRUST_CONFIDENCE_FLOOR} for long_term storage"
                )
            self._tier(memory.layer)[memory.id] = memory
            self._persist()
            return memory

    def get(self, memory_id: str) -> Memory | None:
        with self._lock:
            for tier in (self._short_term, self._working, self._long_term):
                if memory_id in tier:
                    return tier[memory_id]
            return None

    def update(self, memory: Memory) -> Memory:
        with self._lock:
            # Remove from old tier if layer changed
            for tier in (self._short_term, self._working, self._long_term):
                tier.pop(memory.id, None)
            if memory.layer == MemoryLayer.LONG_TERM and memory.confidence < HIGH_TRUST_CONFIDENCE_FLOOR:
                raise ValueError("Cannot promote memory below high-trust floor to long_term")
            self._tier(memory.layer)[memory.id] = memory
            self._persist()
            return memory

    def invalidate(self, memory_id: str) -> bool:
        """Invalidate (delete) a memory. Audit handled by caller via ledger."""
        with self._lock:
            for tier in (self._short_term, self._working, self._long_term):
                if tier.pop(memory_id, None) is not None:
                    self._persist()
                    return True
            return False

    def mark_accessed(self, memory_id: str) -> None:
        with self._lock:
            memory = self.get(memory_id)
            if memory:
                memory.access_count += 1
                memory.last_accessed = datetime.now(timezone.utc)
                self._persist()

    # ------------------------------------------------------------------
    # Scoped reads — isolation is enforced here
    # ------------------------------------------------------------------

    def all_for_scope(
        self,
        tenant_id: str,
        investigation_id: str | None = None,
        include_shared: bool = True,
        include_related: bool = False,
    ) -> list[Memory]:
        """Return memories visible to this (tenant, investigation) scope.

        - tenant_id must match exactly (no cross-tenant leakage, ever).
        - When include_related=False (strict scope): investigation-scoped
          memories are visible only to that investigation.
        - When include_related=True: all memories of the same tenant are
          candidates regardless of investigation id — cross-investigation
          correlation with attribution preserved by the caller.
        - Shared knowledge (investigation_id=None) is included when
          include_shared=True.
        """
        with self._lock:
            result: list[Memory] = []
            for tier in (self._short_term, self._working, self._long_term):
                for memory in tier.values():
                    if memory.tenant_id != tenant_id:
                        continue
                    if not include_related:
                        if memory.investigation_id is not None and memory.investigation_id != investigation_id:
                            continue
                        if memory.investigation_id is None and not include_shared:
                            continue
                    result.append(memory)
            return result

    def count(self) -> dict[str, int]:
        with self._lock:
            return {
                "short_term": len(self._short_term),
                "working": len(self._working),
                "long_term": len(self._long_term),
            }
