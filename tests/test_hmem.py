"""H-MEM conformance-style tests against the canonical contracts.

Covers: mandatory source rejection, tiered storage, trust floor on
long_term, hybrid retrieval formula + threshold + trace, feedback deltas
(spec §9.2 exact values), conflict detection + supersede suppression,
tenant/investigation isolation, invalidate, audit trail, health status.
"""

from __future__ import annotations

import pytest

from hmem.engine import HMemEngine
from hmem.models import (
    FEEDBACK_DELTAS,
    HIGH_TRUST_CONFIDENCE_FLOOR,
    RETRIEVAL_THRESHOLD_FALLBACK as RETRIEVAL_THRESHOLD,
    Entity,
    Memory,
    MemoryType,
    MemoryLayer,
    Provenance,
    ProvenanceOrigin,
)
from datetime import datetime, timezone


def _prov(label: str = "test") -> Provenance:
    return Provenance(origin=ProvenanceOrigin.DIRECT_CAPTURE, learned_at=datetime.now(timezone.utc), label=label)


@pytest.fixture()
def engine(tmp_path):
    return HMemEngine(data_dir=tmp_path / "hmem", actor="test")


# --- Canonical record -------------------------------------------------------

def test_source_mandatory():
    with pytest.raises(ValueError, match="source"):
        Memory(content="x", type=MemoryType.FACTUAL, source="", provenance=_prov())


def test_entity_cap():
    with pytest.raises(ValueError, match="Entity cap"):
        Memory(
            content="x",
            type=MemoryType.FACTUAL,
            source="s",
            provenance=_prov(),
            entities=tuple(Entity(name=f"e{i}", entity_type="concept") for i in range(11)),
        )


def test_confidence_clamped():
    m = Memory(content="x", type=MemoryType.FACTUAL, source="s", provenance=_prov(), confidence=1.5)
    assert m.confidence == 1.0


# --- Trust floor ------------------------------------------------------------

def test_long_term_rejects_low_confidence(engine):
    with pytest.raises(ValueError, match="high-trust floor"):
        engine.remember(
            "unverified rumor about evil.example",
            tenant_id="t1",
            layer=MemoryLayer.LONG_TERM,
            source="unverified_web",
            provenance_label="rumor",
            confidence=HIGH_TRUST_CONFIDENCE_FLOOR - 0.01,
        )


def test_long_term_accepts_high_confidence(engine):
    m = engine.remember(
        "evil.example confirmed phishing by zetaris lookup",
        tenant_id="t1",
        layer=MemoryLayer.LONG_TERM,
        source="zetaris:threat_indicators",
        provenance_label="Zetaris IOC match",
        confidence=0.9,
    )
    assert m.layer == MemoryLayer.LONG_TERM


# --- Retrieval --------------------------------------------------------------

def test_retrieval_returns_trace_and_above_threshold(engine):
    engine.remember(
        "Domain evil.example was confirmed as a phishing indicator",
        tenant_id="t1",
        investigation_id="inv-1",
        source="investigation",
        provenance_label="inv-1 finding",
        entities=(Entity(name="evil.example", entity_type="domain"),),
        tags=("phishing",),
        domain="evil.example",
        confidence=0.95,
    )
    result = engine.recall("is evil.example phishing?", tenant_id="t1", investigation_id="inv-1")
    assert len(result.memories) >= 1
    assert result.traces[0].relevance_score >= RETRIEVAL_THRESHOLD
    assert result.traces[0].retrieval_reason
    assert "semantic" in result.traces[0].score_components
    assert result.traces[0].strategy == "comprehensive"


def test_retrieval_excludes_below_threshold(engine):
    engine.remember(
        "completely unrelated fact about weather patterns",
        tenant_id="t1",
        investigation_id="inv-1",
        source="investigation",
        provenance_label="x",
        confidence=0.4,
    )
    result = engine.recall("quantum entanglement zebra finance", tenant_id="t1", investigation_id="inv-1")
    assert all(tr.relevance_score >= RETRIEVAL_THRESHOLD for tr in result.traces)


def test_superseded_memory_penalized(engine):
    old = engine.remember(
        "evil.example is safe",
        tenant_id="t1",
        investigation_id="inv-1",
        source="investigation",
        provenance_label="old",
        confidence=0.9,
        entities=(Entity(name="evil.example", entity_type="domain"),),
    )
    new = engine.remember(
        "evil.example is malicious phishing",
        tenant_id="t1",
        investigation_id="inv-1",
        source="investigation",
        provenance_label="correction",
        confidence=0.9,
        supersedes=old.id,
        entities=(Entity(name="evil.example", entity_type="domain"),),
    )
    old_stored = engine.store.get(old.id)
    old_stored.superseded_by = new.id
    engine.store.update(old_stored)
    result = engine.recall("evil.example", tenant_id="t1", investigation_id="inv-1")
    scores = {m.id: tr.relevance_score for m, tr in zip(result.memories, result.traces)}
    assert new.id in scores, "correction memory should be retrieved"
    if old.id in scores:
        assert scores[new.id] > scores[old.id], "superseded memory must score lower than its replacement"


# --- Feedback deltas (spec §9.2 exact) --------------------------------------

def test_feedback_helpful_delta(engine):
    m = engine.remember("fact", tenant_id="t1", source="s", provenance_label="p", confidence=0.5)
    updated = engine.feedback(m.id, "helpful")
    assert updated.confidence == pytest.approx(0.5 + 0.05)
    assert updated.access_count == 1


def test_feedback_not_helpful_delta(engine):
    m = engine.remember("fact", tenant_id="t1", source="s", provenance_label="p", confidence=0.5)
    updated = engine.feedback(m.id, "not_helpful")
    assert updated.confidence == pytest.approx(0.5 - 0.03)


def test_feedback_wrong_delta_and_review_tag(engine):
    m = engine.remember("fact", tenant_id="t1", source="s", provenance_label="p", confidence=0.5)
    updated = engine.feedback(m.id, "wrong")
    assert updated.confidence == pytest.approx(0.5 - 0.20)
    assert "review" in updated.tags


def test_feedback_deltas_match_spec():
    assert FEEDBACK_DELTAS == {"helpful": 0.05, "not_helpful": -0.03, "wrong": -0.20}


# --- Isolation ----------------------------------------------------------------

def test_no_cross_tenant_leakage(engine):
    engine.remember("tenant-1 secret", tenant_id="t1", investigation_id="i1", source="s", provenance_label="p")
    result = engine.recall("secret", tenant_id="t2", investigation_id="i1")
    assert len(result.memories) == 0


def test_no_cross_investigation_leakage(engine):
    """Strict scoping: with include_related_investigations=False, a memory
    from investigation i1 is invisible to investigation i2."""
    engine.remember("investigation-one finding", tenant_id="t1", investigation_id="i1", source="s", provenance_label="p")
    result = engine.recall(
        "finding", tenant_id="t1", investigation_id="i2", include_related_investigations=False
    )
    assert len(result.memories) == 0


def test_related_investigations_correlation_opt_in(engine):
    """Default recall correlates across same-tenant investigations."""
    engine.remember(
        "phish-domain.example confirmed suspicious in earlier investigation",
        tenant_id="t1",
        investigation_id="i1",
        source="s",
        provenance_label="p",
    )
    result = engine.recall("phish-domain.example", tenant_id="t1", investigation_id="i2")
    assert len(result.memories) == 1
    assert result.memories[0].investigation_id == "i1"


def test_shared_knowledge_visible_across_investigations(engine):
    engine.remember(
        "shared tenant knowledge",
        tenant_id="t1",
        investigation_id=None,
        layer=MemoryLayer.LONG_TERM,
        source="s",
        provenance_label="p",
        confidence=0.9,
    )
    result = engine.recall("shared knowledge", tenant_id="t1", investigation_id="i2")
    assert len(result.memories) == 1


# --- Conflicts ----------------------------------------------------------------

def test_conflict_detected_on_opposing_claims(engine):
    engine.remember(
        "evil.example is safe",
        tenant_id="t1",
        investigation_id="i1",
        source="s",
        provenance_label="p",
        entities=(Entity(name="evil.example", entity_type="domain"),),
    )
    engine.remember(
        "evil.example is malicious",
        tenant_id="t1",
        investigation_id="i1",
        source="s",
        provenance_label="p",
        entities=(Entity(name="evil.example", entity_type="domain"),),
    )
    conflicts = engine.scan_conflicts(tenant_id="t1", investigation_id="i1")
    assert len(conflicts) == 1
    assert "opposing" in conflicts[0].reason


def test_supersede_relation_suppresses_conflict(engine):
    a = engine.remember("evil.example is safe", tenant_id="t1", source="s", provenance_label="p")
    engine.remember("evil.example is malicious", tenant_id="t1", source="s", provenance_label="p", supersedes=a.id)
    conflicts = engine.scan_conflicts(tenant_id="t1")
    assert conflicts == []


# --- Invalidate + audit --------------------------------------------------------

def test_invalidate_removes_and_audits(engine):
    m = engine.remember("stale fact", tenant_id="t1", source="s", provenance_label="p")
    assert engine.invalidate(m.id)
    assert engine.store.get(m.id) is None
    actions = [e.action.value for e in engine.ledger.entries_for(m.id)]
    assert actions == ["create", "delete"]


def test_audit_trail_records_reads(engine):
    m = engine.remember("audit me", tenant_id="t1", investigation_id="i1", source="s", provenance_label="p")
    engine.recall("audit", tenant_id="t1", investigation_id="i1")
    actions = [e.action.value for e in engine.ledger.entries_for(m.id)]
    assert "create" in actions and "read" in actions


# --- Persistence across engine restart ----------------------------------------

def test_working_and_long_term_persist(tmp_path):
    data_dir = tmp_path / "hmem"
    e1 = HMemEngine(data_dir=data_dir)
    e1.remember("durable fact", tenant_id="t1", source="s", provenance_label="p", layer=MemoryLayer.LONG_TERM, confidence=0.9)
    e2 = HMemEngine(data_dir=data_dir)
    result = e2.recall("durable fact", tenant_id="t1")
    assert len(result.memories) == 1


# --- Health --------------------------------------------------------------------

def test_health_truthful(engine):
    health = engine.health()
    assert health["status"] == "available"
    assert health["dreaming"] == "not_implemented"
    assert health["sleep_cycle"] == "not_implemented"
