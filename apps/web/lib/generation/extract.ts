/**
 * Typed readers over artifact `content`.
 *
 * Artifact content is model-generated. It matches the agent contracts in
 * `apps/api/app/agents/models.py` when the run went well, but a field can be
 * missing, empty, or the wrong shape, and a generator that assumes otherwise
 * produces a blank screen at exactly the wrong moment.
 *
 * So nothing here throws. Every reader narrows what it can and drops what it
 * cannot, and callers decide what to do with an empty result. The cost of a
 * missing field is one absent section, never a failed render.
 */

import type { ArtifactDetail } from "@/lib/api";

/** Content bag off an artifact, always an object. */
export type Content = Record<string, unknown>;

export function contentOf(artifact: ArtifactDetail | undefined): Content {
  return (artifact?.content ?? {}) as Content;
}

export function str(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : fallback;
}

export function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function bool(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

/** A list of plain strings, dropping anything that is not one. */
export function strList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

/** A list of objects, dropping primitives and nulls. */
export function objList(value: unknown): Content[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is Content => typeof item === "object" && item !== null && !Array.isArray(item),
  );
}

// --- Domain readers ---------------------------------------------------------

export interface RequirementLike {
  id: string;
  title: string;
  description: string;
  priority: string;
  rationale: string;
}

export function requirements(content: Content, key: string): RequirementLike[] {
  return objList(content[key]).map((item, index) => ({
    id: str(item.id, `R-${index + 1}`),
    title: str(item.title, "Untitled requirement"),
    description: str(item.description),
    priority: str(item.priority, "should"),
    rationale: str(item.rationale),
  }));
}

export interface UserStoryLike {
  id: string;
  asA: string;
  iWant: string;
  soThat: string;
  acceptanceCriteria: string[];
}

export function userStories(content: Content): UserStoryLike[] {
  return objList(content.user_stories).map((item, index) => ({
    id: str(item.id, `US-${index + 1}`),
    asA: str(item.as_a, "user"),
    iWant: str(item.i_want),
    soThat: str(item.so_that),
    acceptanceCriteria: strList(item.acceptance_criteria),
  }));
}

export interface ComponentLike {
  name: string;
  responsibility: string;
  dependsOn: string[];
}

export function components(content: Content): ComponentLike[] {
  return objList(content.components).map((item) => ({
    name: str(item.name, "Component"),
    responsibility: str(item.responsibility),
    dependsOn: strList(item.depends_on),
  }));
}

export interface EntityLike {
  name: string;
  purpose: string;
  fields: Array<{ name: string; type: string; nullable: boolean; description: string }>;
  relationships: string[];
}

export function entities(content: Content): EntityLike[] {
  return objList(content.entities).map((item) => ({
    name: str(item.name, "Record"),
    purpose: str(item.purpose),
    fields: objList(item.fields).map((field) => ({
      name: str(field.name, "field"),
      type: str(field.type, "text"),
      nullable: bool(field.nullable),
      description: str(field.description),
    })),
    relationships: strList(item.relationships),
  }));
}

export interface EndpointLike {
  method: string;
  path: string;
  purpose: string;
}

export function endpoints(content: Content): EndpointLike[] {
  return objList(content.endpoints).map((item) => ({
    method: str(item.method, "GET").toUpperCase(),
    path: str(item.path, "/"),
    purpose: str(item.purpose),
  }));
}

export interface ChoiceLike {
  layer: string;
  choice: string;
  rationale: string;
}

export function choices(content: Content): ChoiceLike[] {
  return objList(content.choices).map((item) => ({
    layer: str(item.layer, "layer"),
    choice: str(item.choice, "—"),
    rationale: str(item.rationale),
  }));
}

export interface RiskLike {
  description: string;
  impact: string;
  likelihood: string;
  mitigation: string;
}

export function risks(content: Content): RiskLike[] {
  return objList(content.risks).map((item) => ({
    description: str(item.description, "Unnamed risk"),
    impact: str(item.impact, "medium"),
    likelihood: str(item.likelihood, "possible"),
    mitigation: str(item.mitigation),
  }));
}

export interface TaskLike {
  id: string;
  title: string;
  component: string;
  estimate: string;
}

export function tasks(content: Content): TaskLike[] {
  return objList(content.tasks).map((item, index) => ({
    id: str(item.id, `T-${index + 1}`),
    title: str(item.title, "Task"),
    component: str(item.component),
    estimate: str(item.estimate),
  }));
}

export interface CoverageLike {
  covered: number;
  total: number;
}

export function coverage(content: Content): CoverageLike {
  const entries = objList(content.entries);
  const total = num(content.total, entries.length);
  const covered = num(content.covered, entries.filter((entry) => bool(entry.covered)).length);
  return { covered, total };
}
