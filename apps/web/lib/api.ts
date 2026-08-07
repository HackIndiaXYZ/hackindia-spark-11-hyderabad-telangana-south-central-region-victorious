/**
 * Typed bindings for the Victorious API.
 *
 * Types mirror the response models in `apps/api/app/api/schemas.py`. They are
 * hand-written rather than generated: the surface is small, and a generated
 * client would add a build step to a 24-hour project for little gain. The API's
 * OpenAPI schema at `/openapi.json` remains the source of truth if they drift.
 */

import { apiRequest } from "@/lib/api-client";

export type LifecycleStage =
  | "idea"
  | "requirement_discovery"
  | "business_validation"
  | "architecture"
  | "development_planning"
  | "implementation"
  | "testing"
  | "documentation"
  | "deployment_preparation";

export type StageStatus =
  | "pending"
  | "in_progress"
  | "awaiting_approval"
  | "completed"
  | "blocked";

export type ArtifactStatus = "draft" | "awaiting_approval" | "approved" | "rejected";

export type ApprovalStatus = "pending" | "approved" | "rejected" | "changes_requested";

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  current_stage: LifecycleStage;
  completed_stages: number;
  total_stages: number;
  artifact_count: number;
  pending_approvals: number;
  updated_at: string;
}

export interface StageSummary {
  stage: LifecycleStage;
  status: StageStatus;
  owner_role: string | null;
  owner_title: string | null;
  started_at: string | null;
  completed_at: string | null;
  artifact_count: number;
}

export interface ProjectDetail extends ProjectSummary {
  stages: StageSummary[];
}

export interface ArtifactSummary {
  id: string;
  project_id: string;
  type: string;
  title: string;
  stage: LifecycleStage;
  owner_role: string;
  owner_title: string;
  status: ArtifactStatus;
  current_version: number;
  is_stale: boolean;
  updated_at: string;
}

export interface VersionSummary {
  version: number;
  summary: string;
  confidence: number | null;
  produced_by_run_id: string | null;
  created_at: string;
}

export interface ArtifactDetail extends ArtifactSummary {
  version: number;
  body_markdown: string;
  content: Record<string, unknown>;
  version_summary: string;
  confidence: number | null;
  produced_by_run_id: string | null;
  is_latest: boolean;
  versions: VersionSummary[];
  /** The review of *this* version. Null for versions no agent produced. */
  review: ReviewView | null;
}

export interface AgentCard {
  stage: LifecycleStage;
  role: string;
  title: string;
  status: string;
  task: string;
  reasoning_summary: string;
  confidence: number | null;
  input_artifact_ids: string[];
  output_artifact_ids: string[];
  blocked_on: string[];
  provider: string | null;
  model: string | null;
  total_tokens: number;
  duration_seconds: number | null;
  run_id: string | null;
  started_at: string | null;
}

export interface ImpactedArtifactView {
  artifact_id: string;
  title: string;
  type: string | null;
  depth: number;
  via_kind: string;
}

export interface ApprovalView {
  id: string;
  project_id: string;
  project_name: string;
  kind: string;
  stage: LifecycleStage;
  title: string;
  what_changed: string;
  why: string;
  requested_by: string;
  agents_involved: string[];
  agent_titles: string[];
  artifacts: ArtifactSummary[];
  impacted: ImpactedArtifactView[];
  status: ApprovalStatus;
  feedback: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface EventView {
  id: string;
  type: string;
  stage: LifecycleStage | null;
  role: string | null;
  role_title: string | null;
  summary: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AdvanceResponse {
  project_id: string;
  executed_stages: LifecycleStage[];
  halt_action: string | null;
  halt_reason: string;
  pending_approval_id: string | null;
  conflicts: Array<Record<string, unknown>>;
  error: string | null;
}

export interface ImpactPreview {
  artifact_id: string;
  artifact_title: string;
  impacted: ImpactedArtifactView[];
  stages_affected: LifecycleStage[];
}

export type ReviewVerdict =
  | "approved"
  | "approved_with_suggestions"
  | "needs_revision";

export interface ReviewFindingView {
  text: string;
  /** "check" for a deterministic rule, "reasoning" for a model judgement. */
  source: string;
}

export interface ReviewView {
  id: string;
  artifact_id: string;
  artifact_title: string;
  artifact_type: string | null;
  artifact_version: number;
  stage: LifecycleStage;
  role: string;
  role_title: string;
  quality_score: number;
  deterministic_score: number;
  band: string;
  verdict: ReviewVerdict;
  summary: string;
  strengths: ReviewFindingView[];
  weaknesses: ReviewFindingView[];
  suggestions: ReviewFindingView[];
  reasoning_applied: boolean;
  reviewer_provider: string | null;
  reviewer_model: string | null;
  created_at: string;
}

export interface RoleScore {
  role: string;
  role_title: string;
  average_score: number;
  artifacts_reviewed: number;
  lowest_score: number;
  needs_revision: number;
}

export interface ProjectReviewSummary {
  project_id: string;
  overall_score: number;
  artifacts_reviewed: number;
  reasoning_coverage: number;
  needs_revision: number;
  by_role: RoleScore[];
  recommendations: ReviewFindingView[];
  reviews: ReviewView[];
}

export interface TraceNode {
  id: string;
  title: string;
  type: string;
  stage: LifecycleStage;
  role: string;
  version: number;
  is_stale: boolean;
}

export interface TraceEdgeView {
  id: string;
  upstream_artifact_id: string;
  downstream_artifact_id: string;
  kind: string;
  upstream_version: number;
  current_upstream_version: number;
  is_stale: boolean;
  rationale: string;
}

export interface TraceGraph {
  project_id: string;
  nodes: TraceNode[];
  edges: TraceEdgeView[];
  stale_artifact_ids: string[];
}

const V1 = "/api/v1";

/**
 * Workspace reads must never be served stale.
 *
 * The organization mutates project state on every advance, so a cached response
 * would show a user an artifact list from before the agent that produced it ran.
 */
const live = { cache: "no-store" } as const;

export const api = {
  listProjects: () => apiRequest<ProjectSummary[]>(`${V1}/projects`, live),

  getProject: (id: string) => apiRequest<ProjectDetail>(`${V1}/projects/${id}`, live),

  createProject: (name: string, description: string) =>
    apiRequest<ProjectSummary>(`${V1}/projects`, {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),

  advance: (id: string) =>
    apiRequest<AdvanceResponse>(`${V1}/projects/${id}/advance`, {
      method: "POST",
      // The organization may run several stages before it needs a human.
      timeoutMs: 300_000,
    }),

  listArtifacts: (id: string, params?: { stage?: string; type?: string }) => {
    const query = new URLSearchParams();
    if (params?.stage) query.set("stage", params.stage);
    if (params?.type) query.set("type", params.type);
    const suffix = query.size > 0 ? `?${query}` : "";
    return apiRequest<ArtifactSummary[]>(`${V1}/projects/${id}/artifacts${suffix}`, live);
  },

  getArtifact: (projectId: string, artifactId: string, version?: number) =>
    apiRequest<ArtifactDetail>(
      `${V1}/projects/${projectId}/artifacts/${artifactId}` +
        (version ? `?version=${version}` : ""),
      live,
    ),

  getImpact: (projectId: string, artifactId: string) =>
    apiRequest<ImpactPreview>(
      `${V1}/projects/${projectId}/artifacts/${artifactId}/impact`,
      live,
    ),

  reviseArtifact: (
    projectId: string,
    artifactId: string,
    bodyMarkdown: string,
    summary?: string,
  ) =>
    apiRequest<ArtifactDetail>(
      `${V1}/projects/${projectId}/artifacts/${artifactId}/revise`,
      {
        method: "POST",
        body: JSON.stringify({
          body_markdown: bodyMarkdown,
          summary: summary ?? "",
        }),
      },
    ),

  getOrganization: (id: string) =>
    apiRequest<AgentCard[]>(`${V1}/projects/${id}/agents`, live),

  listApprovals: (id: string, pendingOnly = false) =>
    apiRequest<ApprovalView[]>(
      `${V1}/projects/${id}/approvals${pendingOnly ? "?pending=true" : ""}`,
      live,
    ),

  listPendingApprovals: () => apiRequest<ApprovalView[]>(`${V1}/approvals`, live),

  decideApproval: (approvalId: string, decision: ApprovalStatus, feedback?: string) =>
    apiRequest<ApprovalView>(`${V1}/approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, feedback: feedback ?? null }),
    }),

  listEvents: (id: string, limit = 200) =>
    apiRequest<EventView[]>(`${V1}/projects/${id}/events?limit=${limit}`, live),

  getReviews: (id: string) =>
    apiRequest<ProjectReviewSummary>(`${V1}/projects/${id}/reviews`, live),

  getTraceability: (id: string) =>
    apiRequest<TraceGraph>(`${V1}/projects/${id}/traceability`, live),
};

/** Human-readable stage label, e.g. "Requirement discovery". */
export function stageLabel(stage: LifecycleStage): string {
  const text = stage.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Human-readable artifact type label, e.g. "API contract". */
export function typeLabel(type: string): string {
  const overrides: Record<string, string> = {
    prd: "PRD",
    api_contract: "API contract",
    api_documentation: "API documentation",
    qa: "QA",
  };
  if (overrides[type]) return overrides[type];
  const text = type.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Map a review score onto the shared StatusBadge vocabulary. */
export function scoreState(
  score: number,
): "complete" | "active" | "waiting" | "blocked" {
  if (score >= 85) return "complete";
  if (score >= 70) return "active";
  if (score >= 60) return "waiting";
  return "blocked";
}

/** Map an engineering state onto the shared StatusBadge vocabulary. */
export function badgeState(
  status: string,
): "complete" | "active" | "waiting" | "approval" | "blocked" | "stale" | "idle" {
  switch (status) {
    case "completed":
    case "approved":
      return "complete";
    case "active":
    case "in_progress":
    case "reviewing":
      return "active";
    case "queued":
    case "waiting_on_dependency":
      return "waiting";
    case "awaiting_approval":
    case "pending":
      return "approval";
    case "failed":
    case "blocked":
    case "rejected":
      return "blocked";
    default:
      return "idle";
  }
}
