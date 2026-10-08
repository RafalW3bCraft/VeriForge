export type InputType = "message" | "email" | "url";
export type Verdict = "SAFE" | "LOW" | "SUSPICIOUS" | "HIGH" | "CRITICAL";

export interface Evidence {
  id: string;
  kind: string;
  value: string;
  source: string;
  snippet?: string | null;
  observed: boolean;
}

export interface Finding {
  finding: string;
  severity: "low" | "medium" | "high" | "critical";
  evidence: string;
  source: string;
  confidence: number;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  attributes: Record<string, string | number | boolean>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  evidence_id?: string | null;
}

export interface AgentResult {
  score: number;
  critical_signal: number;
  confidence: number;
  summary: string;
  findings: Finding[];
}

export interface VerificationResult extends AgentResult {
  agreements: string[];
  disagreements: string[];
  contradictions: string[];
  missing_evidence: string[];
  unsupported_claims: string[];
  evidence_strength: number;
}

export interface AnalysisResponse {
  analysis_id: string;
  created_at: string;
  input_type: InputType;
  score: number;
  verdict: Verdict;
  confidence: number;
  risk_decision: {
    risk_score: number;
    confidence: number;
    evidence_strength: number;
    verdict: Verdict;
    recommended_action: string;
  };
  summary: string;
  recommended_action: string;
  extraction: {
    urls: string[];
    domains: string[];
    emails: string[];
    urgency_terms: string[];
    credential_terms: string[];
    financial_terms: string[];
    requests_credentials: boolean;
    requests_financial_action: boolean;
    claims: Array<{ id: string; kind: string; value: string; snippet?: string | null }>;
    evidence: Evidence[];
  };
  findings: Finding[];
  agents: {
    identity: AgentResult;
    infrastructure: AgentResult;
    social_engineering: AgentResult;
    verification: VerificationResult;
  };
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  meta: Record<string, unknown>;
}

export interface AnalysisSummary {
  analysis_id: string;
  created_at: string;
  input_type: InputType;
  score: number;
  verdict: Verdict;
  summary: string;
}

export interface AnalysisListResponse {
  items: AnalysisSummary[];
}