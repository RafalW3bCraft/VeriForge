import type { AnalysisListResponse, AnalysisResponse, InputType, IntegrationsHealth } from "./types";

interface ErrorResponse {
  detail?: string;
  error?: { message?: string };
}

let csrfToken = sessionStorage.getItem("veriforge_csrf") ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface CurrentUser { id: string; username?: string; role: "admin" | "analyst" | "viewer"; tenant_id?: string; }
export interface AdminUser { id: string; username: string; role: "admin" | "analyst" | "viewer"; active: boolean; }
export interface AuditEvent { id: string; actor_id?: string | null; action: string; resource_type: string; resource_id?: string | null; detail: Record<string, unknown>; created_at: string; }

export async function getAuthMode() { return request<{ accounts_enabled: boolean }>("/api/v1/auth/mode"); }
export async function getCurrentUser() { return request<CurrentUser>("/api/v1/auth/me"); }
export async function login(username: string, password: string) {
  const response = await request<{ user: CurrentUser; csrf_token: string }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
  csrfToken = response.csrf_token;
  sessionStorage.setItem("veriforge_csrf", csrfToken);
  return response.user;
}
export async function logout() {
  await request<void>("/api/v1/auth/logout", { method: "POST", headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {} });
  csrfToken = "";
  sessionStorage.removeItem("veriforge_csrf");
}

export function analyze(content: string, inputType: InputType) {
  return request<AnalysisResponse>("/api/v1/analyze", {
    method: "POST",
    headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
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

export function getIntegrationsStatus() {
  return request<IntegrationsHealth>("/api/v1/integrations/status");
}

export function getAdminUsers() {
  return request<{ items: AdminUser[] }>("/api/v1/admin/users");
}

export function getAdminAudit() {
  return request<{ items: AuditEvent[] }>("/api/v1/admin/audit?limit=50");
}

export function createAdminUser(username: string, password: string, role: AdminUser["role"]) {
  return request<AdminUser>("/api/v1/admin/users", {
    method: "POST",
    headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
    body: JSON.stringify({ username, password, role }),
  });
}
