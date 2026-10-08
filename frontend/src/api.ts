import type { AnalysisListResponse, AnalysisResponse, InputType } from "./types";

interface ErrorResponse {
  detail?: string;
  error?: { message?: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as ErrorResponse;
      message = body.error?.message ?? body.detail ?? message;
    } catch {
      // Keep the status-based message when the server did not return JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export function analyze(content: string, inputType: InputType) {
  return request<AnalysisResponse>("/api/v1/analyze", {
    method: "POST",
    body: JSON.stringify({ content, input_type: inputType }),
  });
}

export function listAnalyses(limit = 100) {
  return request<AnalysisListResponse>(`/api/v1/analyses?limit=${limit}`);
}

export function getAnalysis(analysisId: string) {
  return request<AnalysisResponse>(`/api/v1/analyses/${encodeURIComponent(analysisId)}`);
}

export async function getHealth() {
  return request<{ status: string }>("/health");
}