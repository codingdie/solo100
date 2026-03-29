/**
 * solo100 API client
 * Wraps all backend REST endpoints.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  description: string | null;
  repo_url: string;
  branch: string;
  created_at: string;
}

export type FeatureStatus =
  | "pending"
  | "brainstorming"
  | "planning"
  | "implementing"
  | "testing"
  | "reviewing"
  | "approved"
  | "verifying"
  | "merged"
  | "failed";

export interface Feature {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: FeatureStatus;
  current_stage: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeatureExecution {
  id: string;
  feature_id: string;
  stage: string;
  status: string;
  output: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ReviewReport {
  id: string;
  feature_id: string;
  summary: string;
  approved: boolean;
  issues: string[];
  created_at: string;
}

export interface CreateProjectPayload {
  name: string;
  description?: string;
  repo_url: string;
  branch?: string;
}

export interface CreateFeaturePayload {
  title: string;
  description?: string;
}

export interface ApprovalPayload {
  approved: boolean;
  comment?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Projects ─────────────────────────────────────────────────────────────────

export const api = {
  projects: {
    list: () => request<Project[]>("/api/projects"),
    get: (id: string) => request<Project>(`/api/projects/${id}`),
    create: (payload: CreateProjectPayload) =>
      request<Project>("/api/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  features: {
    list: (projectId: string) =>
      request<Feature[]>(`/api/projects/${projectId}/features`),
    get: (featureId: string) =>
      request<Feature>(`/api/features/${featureId}`),
    create: (projectId: string, payload: CreateFeaturePayload) =>
      request<Feature>(`/api/projects/${projectId}/features`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    executions: (featureId: string) =>
      request<FeatureExecution[]>(`/api/features/${featureId}/executions`),
    review: (featureId: string) =>
      request<ReviewReport>(`/api/features/${featureId}/review`),
  },

  approvals: {
    submit: (featureId: string, payload: ApprovalPayload) =>
      request<{ ok: boolean }>(`/api/approvals/${featureId}`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
};
