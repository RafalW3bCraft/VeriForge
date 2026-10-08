import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

describe('App', () => {
  beforeEach(() => {
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

  it('renders the dashboard and can submit analysis', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );

    expect(screen.getByRole('heading', { name: /veriforge/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /analyze message/i })).toBeInTheDocument();

    const textarea = screen.getByLabelText(/message content/i);
    await userEvent.clear(textarea);
    await userEvent.type(textarea, 'URGENT: Your GitHub account is suspended. Verify now at https://github-security-check.zip');

    await userEvent.click(screen.getByRole('button', { name: /analyze message/i }));

    expect(await screen.findByText(/risk score/i)).toBeInTheDocument();
  });
});
