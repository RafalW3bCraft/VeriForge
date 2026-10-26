"""Hybrid retrieval with trace (spec §6).

Canonical scoring formula:
    raw = 0.35·semantic + 0.20·keyword + 0.10·tag + 0.10·domain
        + 0.15·entity   + 0.05·layer   + 0.05·recency − 0.20·superseded
    score = clamp01(raw) × confidence

Semantic similarity uses token-overlap cosine as a model-free fallback
(spec §4.3: graceful degradation when no embedding model is available).
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone

from hmem.models import (
    LAYER_WEIGHTS,
    RETRIEVAL_THRESHOLD_FALLBACK,
    RETRIEVAL_TOP_N,
    Memory,
    RetrievalResult,
    RetrievalTrace,
    clamp01,
)

from hmem.store import MemoryStore

# Model-free fallback scoring uses token overlap instead of embeddings; the
# spec's 0.35 threshold assumes embedding similarity. The fallback threshold
# preserves the spec's top-N and formula while matching fallback score scale.
DEFAULT_THRESHOLD = RETRIEVAL_THRESHOLD_FALLBACK

logger = logging.getLogger("veriforge.hmem.retrieval")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    """Tokenize including domain/host surface forms so 'phish-site-one.example'
    matches both its dotted and hyphenated substrings."""
    base = set(_TOKEN_RE.findall(text.casefold()))
    # Split alnum tokens on internal boundaries already handled; add nothing else.
    return base


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cosine_tokens(a: set[str], b: set[str]) -> float:
    """Model-free semantic proxy: cosine over binary token vectors."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    return intersection / math.sqrt(len(a) * len(b))


class MemoryRetrievalService:
    def __init__(self, store: MemoryStore):
        self._store = store

    def _score(self, query: str, memory: Memory, query_tokens: set[str], now: datetime) -> tuple[float, dict[str, float]]:
        memory_tokens = _tokens(memory.content) | set(memory.tags)
        semantic = _cosine_tokens(query_tokens, memory_tokens)
        keyword = _jaccard(set(sorted(query_tokens)[:8]), memory_tokens)
        tag = _jaccard(query_tokens, set(t.casefold() for t in memory.tags))
        domain = 1.0 if memory.domain and memory.domain.casefold() in query.casefold() else 0.0
        entity_names = {e.name.casefold() for e in memory.entities}
        entity = 1.0 if entity_names & query_tokens else 0.0
        layer = LAYER_WEIGHTS[memory.layer]
        recency = memory.recency_boost(now)
        superseded = 1.0 if memory.is_superseded else 0.0

        raw = (
            0.35 * semantic
            + 0.20 * keyword
            + 0.10 * tag
            + 0.10 * domain
            + 0.15 * entity
            + 0.05 * layer
            + 0.05 * recency
            - 0.20 * superseded
        )
        score = clamp01(raw) * memory.confidence
        components = {
            "semantic": round(semantic, 4),
            "keyword": round(keyword, 4),
            "tag": round(tag, 4),
            "domain": round(domain, 4),
            "entity": round(entity, 4),
            "layer": round(layer, 4),
            "recency": round(recency, 4),
            "superseded": round(superseded, 4),
            "raw": round(raw, 4),
            "confidence": round(memory.confidence, 4),
        }
        return score, components

    def retrieve(
        self,
        query: str,
        tenant_id: str,
        investigation_id: str | None = None,
        top_n: int = RETRIEVAL_TOP_N,
        threshold: float = DEFAULT_THRESHOLD,
        strategy: str = "comprehensive",
        include_related: bool = False,
    ) -> RetrievalResult:
        now = datetime.now(timezone.utc)
        query_tokens = _tokens(query)
        candidates = self._store.all_for_scope(
            tenant_id, investigation_id, include_related=include_related
        )
        scored: list[tuple[Memory, float, dict[str, float]]] = []
        for memory in candidates:
            score, components = self._score(query, memory, query_tokens, now)
            if score >= threshold:
                scored.append((memory, score, components))
        scored.sort(key=lambda item: item[1], reverse=True)
        selected = scored[:top_n]

        memories: list[Memory] = []
        traces: list[RetrievalTrace] = []
        for memory, score, components in selected:
            self._store.mark_accessed(memory.id)
            memory.score = score
            memories.append(memory)
            reasons = [k for k in ("entity", "domain", "keyword", "semantic") if components[k] > 0.3]
            reason = f"matched on {', '.join(reasons)}" if reasons else "low-signal match above threshold"
            traces.append(
                RetrievalTrace(
                    memory_id=memory.id,
                    relevance_score=round(score, 4),
                    strategy=strategy,
                    retrieval_reason=reason,
                    score_components=components,
                )
            )
        return RetrievalResult(
            memories=tuple(memories),
            traces=tuple(traces),
            query=query,
            strategy=strategy,
            retrieved_at=now,
        )
