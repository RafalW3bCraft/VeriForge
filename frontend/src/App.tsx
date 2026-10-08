import { useEffect, useState } from "react";
import { Activity, ArrowRight, Clock3, SearchCheck, ShieldAlert } from "lucide-react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";
import { analyze, getAnalysis, getHealth, listAnalyses } from "./api";
import { scenarios } from "./scenarios";
import type { AnalysisResponse, AnalysisSummary, InputType } from "./types";

function App() {
  const [serviceState, setServiceState] = useState<"checking" | "online" | "offline">(
    "checking",
  );

  useEffect(() => {
    let mounted = true;
    getHealth()
      .then(() => {
        if (mounted) setServiceState("online");
      })
      .catch(() => {
        if (mounted) setServiceState("offline");
      });

    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">V</div>
          <div>
            <div className="brand-name">VeriForge</div>
            <div className="brand-subtitle">Evidence-first phishing and scam analysis</div>
          </div>
        </div>

        <nav className="nav" aria-label="Main navigation">
          <NavLink to="/">Analyze</NavLink>
          <NavLink to="/history">History</NavLink>
          <NavLink to="/live">Live Email</NavLink>
        </nav>

        <div className={`status-pill status-${serviceState}`}>
          {serviceState === "online" && "Backend online"}
          {serviceState === "offline" && "Backend offline"}
          {serviceState === "checking" && "Checking backend"}
        </div>
      </header>

      <main className="page-shell">
        <Routes>
          <Route path="/" element={<AnalyzePage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/live" element={<LivePage />} />
          <Route path="/analysis/:analysisId" element={<AnalysisPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function AnalyzePage() {
  const navigate = useNavigate();
  const [inputType, setInputType] = useState<InputType>("message");
  const [content, setContent] = useState(scenarios[0].content);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleScenario = (scenario: (typeof scenarios)[number]) => {
    setInputType(scenario.type);
    setContent(scenario.content);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await analyze(content.trim(), inputType);
      navigate(`/analysis/${result.analysis_id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "The analysis request failed.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-grid two-column">
      <section className="panel">
        <div className="panel-header">
          <div className="eyebrow">Threat intake</div>
          <h1>Analyze suspicious content</h1>
        </div>

        <form className="analysis-form" onSubmit={handleSubmit}>
          <label className="field-group">
            <span>Input type</span>
            <select value={inputType} onChange={(e) => setInputType(e.target.value as InputType)}>
              <option value="message">Message</option>
              <option value="email">Email</option>
              <option value="url">URL</option>
            </select>
          </label>

          <label className="field-group">
            <span>Content</span>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Paste the suspicious message, email, or URL context here."
              rows={12}
            />
          </label>

          {error && <div className="alert error">{error}</div>}

          <div className="button-row">
            <button className="primary-button" type="submit" disabled={loading || !content.trim()}>
              {loading ? "Analyzing..." : "Run analysis"}
            </button>
          </div>
        </form>
      </section>

      <aside className="panel">
        <div className="panel-header">
          <div className="eyebrow">Sample scenarios</div>
          <h2>Quick checks</h2>
        </div>

        <div className="scenario-list">
          {scenarios.map((scenario) => (
            <button
              key={scenario.id}
              type="button"
              className="scenario-card"
              onClick={() => handleScenario(scenario)}
            >
              <div className="scenario-name">{scenario.name}</div>
              <div className="scenario-meta">{scenario.type}</div>
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
}

function HistoryPage() {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    listAnalyses(20)
      .then((response) => {
        if (active) setItems(response.items ?? []);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "History unavailable.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="panel">
      <div className="panel-header inline-header">
        <div>
          <div className="eyebrow">History</div>
          <h1>Recent analysis records</h1>
        </div>
        <div className="header-stat">{items.length} entries</div>
      </div>

      {loading && <div className="muted">Loading history…</div>}
      {error && <div className="alert error">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">No analyses have been saved yet.</div>
      )}

      <div className="history-list">
        {items.map((item) => (
          <Link key={item.analysis_id} to={`/analysis/${item.analysis_id}`} className="history-card">
            <div className="history-topline">
              <span className={`verdict-badge verdict-${item.verdict.toLowerCase()}`}>
                {item.verdict}
              </span>
              <span className="muted">{new Date(item.created_at).toLocaleString()}</span>
            </div>
            <div className="history-score">{item.score.toFixed(1)} / 100</div>
            <div className="history-summary">{item.summary}</div>
            <div className="history-link">
              Open analysis <ArrowRight size={14} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function LivePage() {
  const navigate = useNavigate();
  const [content, setContent] = useState(
    "From: ceo-office@example.test\nSubject: Urgent wire request\n\nI need this kept private. Please transfer funds before 5 PM and use the updated account details in the secure portal.",
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await analyze(content.trim(), "email");
      navigate(`/analysis/${result.analysis_id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Live analysis failed.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="eyebrow">Live email analysis</div>
        <h1>Monitor incoming suspicious email content</h1>
      </div>

      <form className="analysis-form" onSubmit={handleSubmit}>
        <label className="field-group">
          <span>Email body</span>
          <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={14} />
        </label>

        {error && <div className="alert error">{error}</div>}

        <div className="button-row">
          <button className="primary-button" type="submit" disabled={loading || !content.trim()}>
            {loading ? "Scanning..." : "Run live scan"}
          </button>
        </div>
      </form>
    </div>
  );
}

function AnalysisPage() {
  const { analysisId } = useParams();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysisId) {
      setLoading(false);
      setError("Analysis id is missing.");
      return;
    }

    let active = true;
    getAnalysis(analysisId)
      .then((result) => {
        if (active) setAnalysis(result);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "The analysis could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [analysisId]);

  if (loading) return <div className="panel"><div className="muted">Loading analysis…</div></div>;
  if (error) return <div className="panel"><div className="alert error">{error}</div></div>;
  if (!analysis) return <div className="panel"><div className="empty-state">No analysis data available.</div></div>;

  const totalEvidence = analysis.extraction.evidence.length + analysis.findings.length;

  return (
    <div className="analysis-page">
      <section className="panel summary-panel">
        <div className="panel-header inline-header">
          <div>
            <div className="eyebrow">Analysis result</div>
            <h1>{analysis.analysis_id}</h1>
          </div>
          <div className={`verdict-badge verdict-${analysis.verdict.toLowerCase()}`}>{analysis.verdict}</div>
        </div>

        <div className="metrics-grid">
          <MetricCard icon={<ShieldAlert size={18} />} label="Risk score" value={`${analysis.score.toFixed(1)}/100`} />
          <MetricCard icon={<SearchCheck size={18} />} label="Confidence" value={`${(analysis.confidence * 100).toFixed(0)}%`} />
          <MetricCard icon={<Clock3 size={18} />} label="Evidence" value={String(totalEvidence)} />
          <MetricCard icon={<Activity size={18} />} label="Input" value={analysis.input_type} />
        </div>

        <div className="summary-box">
          <h3>Recommended action</h3>
          <p>{analysis.recommended_action}</p>
        </div>

        <div className="summary-box">
          <h3>Summary</h3>
          <p>{analysis.summary}</p>
        </div>
      </section>

      <section className="content-grid two-column">
        <article className="panel">
          <div className="panel-header">
            <div className="eyebrow">Evidence</div>
            <h2>Signals extracted</h2>
          </div>

          <div className="chip-list">
            {analysis.extraction.urls.map((url) => (
              <span key={url} className="chip">URL: {url}</span>
            ))}
            {analysis.extraction.domains.map((domain) => (
              <span key={domain} className="chip">Domain: {domain}</span>
            ))}
            {analysis.extraction.emails.map((email) => (
              <span key={email} className="chip">Email: {email}</span>
            ))}
            {analysis.extraction.urgency_terms.map((term) => (
              <span key={term} className="chip">Urgency: {term}</span>
            ))}
            {analysis.extraction.credential_terms.map((term) => (
              <span key={term} className="chip">Credential: {term}</span>
            ))}
            {analysis.extraction.financial_terms.map((term) => (
              <span key={term} className="chip">Finance: {term}</span>
            ))}
          </div>

          <div className="list-block">
            {analysis.extraction.evidence.map((evidence) => (
              <div key={evidence.id} className="list-item">
                <div className="list-item-header">
                  <span className="badge">{evidence.kind}</span>
                  <span className={evidence.observed ? "ok-text" : "warn-text"}>
                    {evidence.observed ? "Observed" : "Not observed"}
                  </span>
                </div>
                <div className="list-item-value">{evidence.value}</div>
                {evidence.snippet && <div className="list-item-snippet">{evidence.snippet}</div>}
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div className="eyebrow">Findings</div>
            <h2>Priority alerts</h2>
          </div>

          <div className="list-block">
            {analysis.findings.map((finding, index) => (
              <div key={`${finding.finding}-${index}`} className="list-item">
                <div className="list-item-header">
                  <span className={`badge severity-${finding.severity}`}>{finding.severity}</span>
                  <span className="muted">{finding.source}</span>
                </div>
                <div className="list-item-value">{finding.finding}</div>
                <div className="list-item-snippet">{finding.evidence}</div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div className="eyebrow">Agent review</div>
          <h2>Specialist model scores</h2>
        </div>

        <div className="agent-grid">
          <AgentCard title="Identity" result={analysis.agents.identity} />
          <AgentCard title="Infrastructure" result={analysis.agents.infrastructure} />
          <AgentCard title="Social engineering" result={analysis.agents.social_engineering} />
          <AgentCard title="Verification" result={analysis.agents.verification} />
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div className="eyebrow">Evidence graph</div>
          <h2>Relationship map</h2>
        </div>

        <div className="graph-grid">
          {analysis.graph.nodes.map((node) => (
            <div key={node.id} className="graph-node">
              <div className="graph-node-title">{node.label}</div>
              <div className="graph-node-type">{node.type}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-icon">{icon}</div>
      <div>
        <div className="metric-label">{label}</div>
        <div className="metric-value">{value}</div>
      </div>
    </div>
  );
}

function AgentCard({ title, result }: { title: string; result: AnalysisResponse["agents"][keyof AnalysisResponse["agents"]] }) {
  const score = (result.score ?? 0).toFixed(1);
  const confidence = ((result.confidence ?? 0) * 100).toFixed(0);

  return (
    <div className="agent-card">
      <div className="list-item-header">
        <div className="agent-card-title">{title}</div>
        <span className="badge">{score}</span>
      </div>
      <div className="agent-summary">{result.summary}</div>
      <div className="agent-meta">
        <span className="muted">confidence: {confidence}%</span>
        <span className="muted">critical signal: {(result.critical_signal ?? 0).toFixed(1)}</span>
      </div>
    </div>
  );
}

export default App;
