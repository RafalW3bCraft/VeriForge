import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

describe('App', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;

        if (url === '/health') {
          return {
            ok: true,
            json: async () => ({ status: 'ok' }),
          } as Response;
        }

        if (url === '/api/v1/auth/mode') {
          return {
            ok: true,
            json: async () => ({ accounts_enabled: false }),
          } as Response;
        }

        if (url === '/api/v1/analyze') {
          return {
            ok: true,
            json: async () => ({
              analysis_id: 'analysis-1',
              created_at: new Date().toISOString(),
              input_type: 'message',
              score: 88,
              verdict: 'CRITICAL',
              confidence: 0.9,
              risk_decision: {
                risk_score: 88,
                confidence: 0.9,
                evidence_strength: 0.9,
                verdict: 'CRITICAL',
                recommended_action: 'Stop and verify the sender through official channels.',
              },
              summary: 'Phishing message detected',
              recommended_action: 'Do not click the link.',
              extraction: {
                urls: ['https://github-security-check.zip'],
                domains: ['github-security-check.zip'],
                emails: [],
                urgency_terms: ['URGENT'],
                credential_terms: ['password'],
                financial_terms: [],
                requests_credentials: true,
                requests_financial_action: false,
                claims: [],
                evidence: [],
              },
              findings: [
                {
                  finding: 'Credential lure',
                  severity: 'critical',
                  evidence: 'Urgent password request',
                  source: 'message',
                  confidence: 0.9,
                },
              ],
              agents: {
                identity: {
                  score: 25,
                  critical_signal: 0,
                  confidence: 0.6,
                  summary: 'Identity marker present',
                  findings: [],
                },
                infrastructure: {
                  score: 50,
                  critical_signal: 0,
                  confidence: 0.7,
                  summary: 'Suspicious URL domain',
                  findings: [],
                },
                social_engineering: {
                  score: 80,
                  critical_signal: 90,
                  confidence: 0.9,
                  summary: 'Urgent credential request',
                  findings: [],
                },
                verification: {
                  score: 88,
                  critical_signal: 90,
                  confidence: 0.9,
                  summary: 'Evidence supports phishing intent',
                  findings: [],
                  agreements: ['Urgent call to action'],
                  disagreements: [],
                  contradictions: [],
                  missing_evidence: [],
                  unsupported_claims: [],
                  evidence_strength: 0.9,
                },
              },
              graph: {
                nodes: [
                  { id: 'n1', label: 'https://github-security-check.zip', type: 'url', attributes: {} },
                  { id: 'n2', label: 'credential request', type: 'finding', attributes: {} },
                ],
                edges: [
                  { source: 'n1', target: 'n2', relation: 'supports' },
                ],
              },
              meta: {},
            }),
          } as Response;
        }

        if (url.startsWith('/api/v1/analyses')) {
          return {
            ok: true,
            json: async () => ({
              items: [
                {
                  analysis_id: 'analysis-1',
                  created_at: new Date().toISOString(),
                  input_type: 'message',
                  score: 88,
                  verdict: 'CRITICAL',
                  summary: 'Phishing message detected',
                },
              ],
            }),
          } as Response;
        }

        throw new Error(`Unhandled fetch: ${String(url)}`);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('routes from the dashboard into the guided investigation form', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );

    expect(await screen.findByRole('heading', { name: /veriforge/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /start an investigation/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /help/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('link', { name: /start an investigation/i }));

    expect(await screen.findByRole('heading', { name: /new investigation/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /analyze content/i })).toBeInTheDocument();
    expect(screen.getByText(/do not include passwords/i)).toBeInTheDocument();
  });

  it('filters saved investigations in the client when the API has no filter support', async () => {
    window.history.pushState({}, '', '/history');
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );

    expect(await screen.findByRole('heading', { name: /saved investigations/i })).toBeInTheDocument();
    expect(screen.getByText(/1 of 1 investigations shown/i)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/verdict/i), 'SAFE');
    expect(screen.getByText(/0 of 1 investigations shown/i)).toBeInTheDocument();
    expect(screen.getByText(/no saved investigations match/i)).toBeInTheDocument();
  });

  it('offers the analyst guide from navigation', async () => {
    window.history.pushState({}, '', '/help');
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );

    expect(await screen.findByRole('heading', { name: /using veriforge responsibly/i })).toBeInTheDocument();
    expect(screen.getByText(/verdicts are decision support/i)).toBeInTheDocument();
  });

  it('shows a semantic evidence table and switches to the relationship view', async () => {
    window.history.pushState({}, '', '/analysis/analysis-1');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url === '/api/v1/auth/mode') return { ok: true, json: async () => ({ accounts_enabled: false }) } as Response;
      return {
        ok: true,
        json: async () => ({
        analysis_id: 'analysis-1', created_at: new Date().toISOString(), input_type: 'message', score: 70, verdict: 'HIGH', confidence: 0.8,
        risk_decision: { risk_score: 70, confidence: 0.8, evidence_strength: 0.7, verdict: 'HIGH', recommended_action: 'Verify through an official channel.' },
        summary: 'Suspicious credential lure', recommended_action: 'Verify through an official channel.',
        extraction: { urls: ['https://example.test'], domains: ['example.test'], emails: [], urgency_terms: [], credential_terms: ['password'], financial_terms: [], requests_credentials: true, requests_financial_action: false, claims: [], evidence: [{ id: 'e1', kind: 'url', value: 'https://example.test', source: 'message', observed: true }] },
        findings: [], agents: { verification: { score: 70, critical_signal: 0, confidence: 0.8, summary: '', findings: [], agreements: [], disagreements: [], contradictions: [], missing_evidence: [], unsupported_claims: [], evidence_strength: 0.7 } },
        graph: { nodes: [{ id: 'node-1', label: 'example.test', type: 'domain', attributes: {} }], edges: [] }, meta: {},
        }),
      } as Response;
    }));
    render(<BrowserRouter><App /></BrowserRouter>);

    expect(await screen.findByRole('table', { name: /observed indicators/i })).toBeInTheDocument();
    expect(screen.getByText('https://example.test')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: /relationship view/i }));
    expect(screen.getByRole('tabpanel', { name: /relationship view/i })).toBeInTheDocument();
    expect(screen.getByText('example.test')).toBeInTheDocument();
  });
});
