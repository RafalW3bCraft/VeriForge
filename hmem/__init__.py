"""VeriForge H-MEM engine.

In-process Python implementation of the Meterless H-MEM contracts
(https://github.com/Meterless/Meterless/tree/main/engines/hmem/AGENTS.md).

Implements: canonical memory record, tiered store, hybrid retrieval with
trace, trust ledger, conflict/supersede handling, per-investigation and
per-tenant isolation.

Not implemented (spec-optional, out of critical path): dreaming cycle,
sleep cycle. Conflicts are detected and flagged; auto-resolve gate is
enforced but human review path is surfaced as pending proposals.
"""

from hmem.models import (
    Memory,
    MemoryLayer,
    MemoryType,
    Provenance,
    ProvenanceOrigin,
    TrustLedgerEntry,
    TrustAction,
    Conflict,
    RetrievalTrace,
    RetrievalResult,
)
from hmem.store import MemoryStore
from hmem.retrieval import MemoryRetrievalService
from hmem.ledger import TrustLedger
from hmem.conflicts import ConflictDetectionService
from hmem.engine import HMemEngine, get_hmem_engine, reset_hmem_engine

__all__ = [
    "Memory",
    "MemoryLayer",
    "MemoryType",
    "Provenance",
    "ProvenanceOrigin",
    "TrustLedgerEntry",
    "TrustAction",
    "Conflict",
    "RetrievalTrace",
    "RetrievalResult",
    "MemoryStore",
    "MemoryRetrievalService",
    "TrustLedger",
    "ConflictDetectionService",
    "HMemEngine",
    "get_hmem_engine",
    "reset_hmem_engine",
]
