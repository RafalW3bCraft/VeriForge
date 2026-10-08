import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";
import { analyze, getAnalysis, getHealth, listAnalyses } from "./api";
import { scenarios } from "./scenarios";
import type { AnalysisResponse, AnalysisSummary, InputType } from "./types";

function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Threat intelligence workspace</p>
          <h1>VeriForge</h1>
        </div>
        <nav className="nav">
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/analysis/demo">History</NavLink>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/analysis/:analysisId" element={<AnalysisPage />} />
      </Routes>
    </div>
  );
}

function DashboardPage() {
  const [content, setContent] = useState(scenarios[0].content);
  const [inputType, setInputType] = useState<InputType>("message");
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [status, setStatus] = useState<string>("Checking backend...");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const health = await getHealth();
        setStatus(`Backend connected (${health.status})`);
      } catch {
        setStatus("Backend unavailable");
      }

      try {
        const list = await listAnalyses(10);
        setHistory(list.items);
      } catch {
        setHistory([]);
      }
    };

    void loadDashboard();
  }, []);

  const handleAnalyze = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!content.trim()) {
      setError("Please provide message content to analyze.");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      const analysis = await analyze(content, inputType);
      setResult(analysis);
      const nextSummary: AnalysisSummary = {
        analysis_id: analysis.analysis_id,
        created_at: analysis.created_at,
        input_type: analysis.input_type,
        score: analysis.score,
        verdict: analysis.verdict,
        summary: analysis.summary,
      };
      setHistory((current) => [nextSummary, ...current.filter((item) => item.analysis_id !== analysis.analysis_id)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis request failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="page-grid">
      <section className="panel panel-main">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Signal intake</p>
            <h2>Analyze message</h2>
          </div>
          <span className="badge badge-info">{status}</span>
        </div>

        <form className="analysis-form" onSubmit={handleAnalyze}>
          <div className="field-row">
            <label htmlFor="input-type">Input type</label>
            <select
              id="input-type"
              value={inputType}
              onChange={(event) => setInputType(event.target.value as InputType)}
            >
              <option value="message">Message</option>
              <option value="email">Email</option>
              <option value="url">URL</option>
            </select>
          </div>

          <div className="field-row">
            <label htmlFor="message-content">Message content</label>
            <textarea
              id="message-content"
              aria-label="Message content"
              rows={10}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Paste a suspicious message or email here..."
            />
          </div>

          <div className="scenario-list">
            {scenarios.map((scenario) => (
              <button
                key={scenario.id}
                type="button"
                className="scenario-button"
                onClick={() => {
                  setContent(scenario.content);
                  setInputType(scenario.type);
                }}
              >
                {scenario.name}
              </button>
            ))}
          </div>

          <div className="action-row">
            <button type="submit" className="primary-button" disabled={isSubmitting}>
              {isSubmitting ? "Analyzing..." : "Analyze message"}
            </button>
          </div>

          {error ? <p className="error-text">{error}</p> : null}
        </form>
      </section>

      <section className="panel panel-result">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Latest result</p>
            <h2>Risk overview</h2>
          </div>
        </div>

        {result ? (
          <div className="result-summary">
            <div className="stat-row">
              <span className="stat-label">Verdict</span>
              <strong className={`verdict verdict-${result.verdict.toLowerCase()}`}>{result.verdict}</strong>
            </div>
            <div className="stat-row">
              <span className="stat-label">Risk score</span>
              <strong>{Math.round(result.risk_decision.risk_score)}</strong>
            </div>
            <div className="stat-row">
              <span className="stat-label">Confidence</span>
              <strong>{(result.confidence * 100).toFixed(0)}%</strong>
            </div>
            <p className="summary-copy">{result.summary}</p>
            <p className="recommendation">{result.recommended_action}</p>

            <div className="graph-preview">
              {result.graph.nodes.slice(0, 8).map((node) => (
                <span key={node.id} className="node-pill" title={node.type}>
                  {node.label}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <p>No analysis has been run yet.</p>
            <p>Use a sample phishing message or paste a real threat report to start.</p>
          </div>
        )}
      </section>

      <section className="panel panel-history">
        <div className="panel-header">
          <div>
            <p className="eyebrow">History</p>
            <h2>Saved analyses</h2>
          </div>
        </div>

        <div className="history-list">
          {history.length ? (
            history.map((item) => (
              <Link key={item.analysis_id} to={`/analysis/${item.analysis_id}`} className="history-item">
                <span className={`verdict verdict-${item.verdict.toLowerCase()}`}>{item.verdict}</span>
                <div>
                  <strong>{item.input_type}</strong>
                  <small>{new Date(item.created_at).toLocaleString()}</small>
                </div>
                <span className="score-badge">{Math.round(item.score)}</span>
              </Link>
            ))
          ) : (
            <p className="empty-text">No saved analyses yet.</p>
          )}
        </div>
      </section>
    </main>
  );
}

function AnalysisPage() {
  const { analysisId } = useParams();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysisId) {
      setError("Missing analysis identifier.");
      setLoading(false);
      return;
    }

    const loadAnalysis = async () => {
      try {
        setLoading(true);
        const result = await getAnalysis(analysisId);
        setAnalysis(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to fetch analysis.");
      } finally {
        setLoading(false);
      }
    };

    void loadAnalysis();
  }, [analysisId]);

  const graph = useMemo(() => analysis?.graph ?? { nodes: [], edges: [] }, [analysis]);

  if (loading) {
    return <div className="panel"><p>Loading response…</p></div>;
  }

  if (error || !analysis) {
    return <div className="panel"><p>{error ?? "Analysis not found."}</p></div>;
  }

  return (
    <main className="analysis-page">
      <section className="panel panel-full">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Evidence report</p>
            <h2>{analysis.summary}</h2>
          </div>
          <Link to="/" className="secondary-link">Back to dashboard</Link>
        </div>

        <div className="detail-grid">
          <div className="detail-card">
            <h3>Decision</h3>
            <p className="stat-value">{analysis.verdict}</p>
            <p>Risk score: {Math.round(analysis.risk_decision.risk_score)}</p>
            <p>Evidence strength: {(analysis.risk_decision.evidence_strength * 100).toFixed(0)}%</p>
            <p>{analysis.recommended_action}</p>
          </div>

          <div className="detail-card">
            <h3>Extraction</h3>
            <ul>
              {analysis.extraction.urls.length ? <li>URLs: {analysis.extraction.urls.join(", ")}</li> : <li>No URLs extracted.</li>}
              {analysis.extraction.domains.length ? <li>Domains: {analysis.extraction.domains.join(", ")}</li> : null}
              {analysis.extraction.emails.length ? <li>Emails: {analysis.extraction.emails.join(", ")}</li> : null}
              {analysis.extraction.credential_terms.length ? <li>Credential terms: {analysis.extraction.credential_terms.join(", ")}</li> : null}
            </ul>
          </div>
        </div>
      </section>

      <section className="panel panel-full">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Evidence graph</p>
            <h2>Claim relationships</h2>
          </div>
        </div>

        <div className="graph-grid">
          {graph.nodes.map((node) => (
            <div key={node.id} className="graph-node">
              <strong>{node.label}</strong>
              <span>{node.type}</span>
            </div>
          ))}
        </div>

        <div className="edge-list">
          {graph.edges.map((edge, index) => (
            <div key={`${edge.source}-${edge.target}-${index}`} className="graph-edge">
              <span>{edge.source}</span>
              <span className="relation">{edge.relation}</span>
              <span>{edge.target}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel panel-full">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Findings</p>
            <h2>Agent observations</h2>
          </div>
        </div>

        <div className="findings-list">
          {analysis.findings.map((finding, index) => (
            <div key={`${finding.finding}-${index}`} className="finding-item">
              <p className="finding-title">{finding.finding}</p>
              <p>{finding.evidence}</p>
              <span className={`severity severity-${finding.severity}`}>{finding.severity}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

export default App;
