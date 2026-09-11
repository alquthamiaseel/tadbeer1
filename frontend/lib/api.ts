/**
 * Typed client for the backend API.
 *
 * Runs on the Next.js server, never in the browser. That is what keeps the
 * dashboard password out of the browser: the server holds it, the browser holds
 * only a session cookie. It also means the backend never has to be reachable
 * from the internet when the dashboard is.
 *
 * These types mirror the response models in backend/app/api/routes.py.
 */

const BASE = process.env.API_URL ?? "http://127.0.0.1:8000";
const PASSWORD = process.env.DASHBOARD_PASSWORD ?? "";

export type StageKind = "INGEST" | "PLAN" | "WBS" | "DESIGN" | "PROTOTYPE" | "DONE";

export type StageStatus =
  | "PENDING"
  | "RUNNING"
  | "AWAITING_APPROVAL"
  | "COMPLETE"
  | "FAILED"
  | "SKIPPED";

export type RunStatus =
  | "PENDING"
  | "RUNNING"
  | "AWAITING_APPROVAL"
  | "COMPLETE"
  | "FAILED"
  | "CANCELLED";

export interface Stage {
  id: string;
  kind: StageKind;
  position: number;
  status: StageStatus;
  attempt: number;
  error: string | null;
  duration_seconds: number | null;
  input_tokens: number;
  output_tokens: number;
}

export interface Artifact {
  id: string;
  kind: string;
  name: string;
  version: number;
  data: Record<string, unknown> | null;
  text: string | null;
  created_at: string;
}

export interface AuditRow {
  id: string;
  kind: string;
  target: string;
  ok: boolean;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  detail: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
}

export interface RunSummary {
  id: string;
  title: string;
  status: RunStatus;
  current_stage: StageKind | null;
  created_at: string;
  asana_project_url: string | null;
  github_repo_url: string | null;
  vercel_url: string | null;
}

export interface RunDetail extends RunSummary {
  error: string | null;
  slack_channel_id: string | null;
  slack_thread_ts: string | null;
  stages: Stage[];
  artifacts: Artifact[];
}

export function apiHeaders(): HeadersInit {
  return PASSWORD ? { Authorization: `Bearer ${PASSWORD}` } : {};
}

export function apiUrl(path: string): string {
  return `${BASE}${path}`;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    cache: "no-store",
    ...init,
    headers: { ...apiHeaders(), ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} for ${path}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRuns: () => call<RunSummary[]>("/api/runs"),
  getRun: (id: string) => call<RunDetail>(`/api/runs/${id}`),
  getAudit: (id: string) => call<AuditRow[]>(`/api/runs/${id}/audit`),
  rerun: (id: string, stage: StageKind, feedback?: string) =>
    call<RunDetail>(`/api/runs/${id}/rerun`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, feedback: feedback || null }),
    }),
  health: () => call<{ status: string }>("/health"),
};
