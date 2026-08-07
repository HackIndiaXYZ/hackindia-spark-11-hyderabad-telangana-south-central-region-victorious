/**
 * The generated-application intermediate representation.
 *
 * This is the contract between *reading artifacts* and *rendering an interface*,
 * and it is the reason the feature is more than a template with holes in it.
 * Synthesis (`synthesize.ts`) turns the organization's artifacts into an
 * `AppSpec`; the renderer (`components/generated/`) knows nothing about
 * artifacts and only walks this tree.
 *
 * Keeping that seam sharp buys two things:
 *
 * - A second consumer can walk the same `AppSpec` and emit files instead of
 *   React elements. That is the whole path to downloadable projects, and it
 *   needs no change to synthesis.
 * - Synthesis is pure data-in/data-out, so it is inspectable and testable
 *   without rendering anything.
 *
 * Every node carries `sourceArtifactIds`. A generated interface that cannot say
 * which requirement produced a given button is a mockup; one that can is a
 * traceable derivation, which is the claim this platform actually makes.
 */

/** Where a piece of generated UI came from. */
export interface Provenance {
  /** Artifact ids that contributed. Empty means synthesised from project metadata. */
  sourceArtifactIds: string[];
  /** Human-readable derivation, e.g. "database_schema → entities[0]". */
  rule: string;
}

/** A colour theme derived from the project rather than picked at random. */
export interface GeneratedTheme {
  /** Base hue in degrees, derived deterministically from the project identity. */
  hue: number;
  name: string;
  /** OKLCH strings, ready for CSS custom properties. */
  accent: string;
  accentSoft: string;
  accentContrast: string;
  surface: string;
  surfaceRaised: string;
  canvas: string;
  border: string;
  content: string;
  contentMuted: string;
  contentSubtle: string;
}

/** A field on a generated form or table column. */
export interface FieldSpec {
  name: string;
  label: string;
  /** Control to render. Derived from the storage type in the schema artifact. */
  control: "text" | "textarea" | "number" | "date" | "datetime" | "select" | "checkbox";
  required: boolean;
  description: string;
  /** Options for `select`, derived from the field name where recognisable. */
  options: string[];
  /** Whether this column leads the table. Exactly one field per entity is primary. */
  primary: boolean;
}

/** A domain object the generated app manages. */
export interface EntitySpec {
  name: string;
  /** Pluralised display name, e.g. "Patients". */
  plural: string;
  purpose: string;
  fields: FieldSpec[];
  relationships: string[];
  /** Endpoints the API contract exposes for this entity. */
  endpoints: EndpointSpec[];
  /** Deterministic sample rows, so tables and charts render populated. */
  rows: Array<Record<string, string | number | boolean>>;
}

export interface EndpointSpec {
  method: string;
  path: string;
  purpose: string;
}

export interface MetricSpec {
  label: string;
  value: number;
  suffix?: string;
  hint: string;
  /** Drives the accent used on the tile. */
  tone: "neutral" | "positive" | "warning" | "critical";
}

export interface FeatureSpec {
  id: string;
  title: string;
  description: string;
  priority: string;
}

export interface FlowStep {
  role: string;
  wants: string;
  soThat: string;
  criteria: string[];
}

export interface ChartSeriesPoint {
  label: string;
  value: number;
}

/** A renderable region of a generated page. */
export type Block =
  | { kind: "hero"; headline: string; sub: string; audiences: string[]; primaryAction: string; provenance: Provenance }
  | { kind: "metrics"; items: MetricSpec[]; provenance: Provenance }
  | { kind: "features"; title: string; items: FeatureSpec[]; provenance: Provenance }
  | { kind: "table"; title: string; entity: EntitySpec; provenance: Provenance }
  | { kind: "form"; title: string; entity: EntitySpec; submitLabel: string; provenance: Provenance }
  | { kind: "chart"; title: string; caption: string; variant: "donut" | "bars"; series: ChartSeriesPoint[]; provenance: Provenance }
  | { kind: "flows"; title: string; steps: FlowStep[]; provenance: Provenance }
  | { kind: "checklist"; title: string; caption: string; items: string[]; provenance: Provenance }
  | { kind: "stack"; title: string; items: Array<{ layer: string; choice: string; rationale: string }>; provenance: Provenance }
  | { kind: "prose"; title: string; markdown: string; provenance: Provenance };

export type PageKind = "landing" | "dashboard" | "entity" | "content";

export interface GeneratedPage {
  /** Route slug within the generated app, e.g. "patients". "" is the landing page. */
  id: string;
  title: string;
  kind: PageKind;
  /** One line under the page title inside the generated app. */
  description: string;
  blocks: Block[];
}

export interface NavItem {
  pageId: string;
  label: string;
  /** Lucide icon name, resolved by the renderer. */
  icon: string;
}

export interface AppSpec {
  brand: {
    name: string;
    tagline: string;
    initials: string;
  };
  theme: GeneratedTheme;
  nav: NavItem[];
  pages: GeneratedPage[];
  /** Counts shown in the generation summary, so the demo can state what it used. */
  stats: {
    artifactsRead: number;
    requirements: number;
    entities: number;
    endpoints: number;
    components: number;
    userStories: number;
    blocks: number;
  };
  /** Every synthesis rule that fired, in order. The "show your working" panel. */
  derivation: Provenance[];
}
