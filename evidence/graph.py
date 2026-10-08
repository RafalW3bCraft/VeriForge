import hashlib

from models import AgentResult, EvidenceGraph, ExtractionResult, GraphEdge, GraphNode, RiskDecision


def _finding_id(agent_name: str, index: int, finding_name: str) -> str:
    key = f"{agent_name}\0{index}\0{finding_name}".encode("utf-8")
    return f"finding-{hashlib.sha256(key).hexdigest()[:16]}"


def build_evidence_graph(
    extraction: ExtractionResult,
    agents: dict[str, AgentResult],
    decision: RiskDecision,
) -> EvidenceGraph:
    nodes: dict[str, GraphNode] = {
        "message": GraphNode(
            id="message", label="Analyzed message", type="input"
        ),
        "risk-decision": GraphNode(
            id="risk-decision",
            label=f"{decision.verdict} ({decision.risk_score:g})",
            type="decision",
            attributes={
                "risk_score": decision.risk_score,
                "confidence": decision.confidence,
                "evidence_strength": decision.evidence_strength,
            },
        ),
    }
    edges: list[GraphEdge] = []

    for claim in extraction.claims:
        nodes[claim.id] = GraphNode(
            id=claim.id,
            label=f"{claim.kind}: {claim.value}",
            type="claim",
            attributes={"source": claim.source, "confidence": claim.confidence},
        )
        edges.append(GraphEdge(
            source="message", target=claim.id, relation="contains_claim"
        ))

    for evidence in extraction.evidence:
        nodes[evidence.id] = GraphNode(
            id=evidence.id,
            label=evidence.value,
            type=evidence.kind,
            attributes={
                "source": evidence.source,
                "observed": evidence.observed,
                "snippet": evidence.snippet or "",
            },
        )
        matching_claims = [
            claim for claim in extraction.claims
            if claim.kind == evidence.kind and claim.value == evidence.value
        ]
        for claim in matching_claims:
            edges.append(GraphEdge(
                source=claim.id,
                target=evidence.id,
                relation="supported_by",
                evidence_id=evidence.id,
            ))

    for agent_name, result in agents.items():
        agent_id = f"agent-{agent_name}"
        nodes[agent_id] = GraphNode(
            id=agent_id,
            label=f"{agent_name.replace('_', ' ').title()} Agent",
            type="agent",
        )
        for index, finding in enumerate(result.findings):
            finding_id = _finding_id(agent_name, index, finding.finding)
            nodes[finding_id] = GraphNode(
                id=finding_id,
                label=finding.finding,
                type="finding",
                attributes={
                    "severity": finding.severity,
                    "confidence": finding.confidence,
                    "source": finding.source,
                    "evidence": finding.evidence,
                },
            )
            edges.append(GraphEdge(
                source=finding_id,
                target=agent_id,
                relation="detected_by",
            ))
            finding_evidence = finding.evidence.casefold()
            for evidence in extraction.evidence:
                if evidence.value.casefold() in finding_evidence:
                    edges.append(GraphEdge(
                        source=evidence.id,
                        target=finding_id,
                        relation="supports",
                        evidence_id=evidence.id,
                    ))
        edges.append(GraphEdge(
            source=agent_id,
            target="risk-decision",
            relation="contributes_to",
        ))

    return EvidenceGraph(nodes=list(nodes.values()), edges=edges)