/**
 * Artifacts → `AppSpec`.
 *
 * The heart of the feature, and deliberately a *pure function*: it takes the
 * artifacts the organization already produced and returns a specification for an
 * application. No network, no model call, no randomness.
 *
 * That last point is the one worth defending. It would be easy to hand the
 * artifacts to an LLM and ask for a UI, but then the demo needs a key, takes
 * thirty seconds, and produces something different every run — and, worse,
 * nothing in the output would be *traceable* to a requirement. Deriving the
 * interface structurally means every screen can name the artifact that caused
 * it, which is the claim this platform actually makes about engineering work.
 *
 * The mapping, in one table:
 *
 * | Artifact                    | Becomes                                  |
 * | --------------------------- | ---------------------------------------- |
 * | `prd.objective`             | Landing hero                             |
 * | `prd.functional_requirements` | Feature cards                          |
 * | `prd.target_users`          | Audience chips, and the nav's shape      |
 * | `database_schema.entities`  | A page per entity: table + create form   |
 * | `database_schema.fields[].type` | Form control per field               |
 * | `api_contract.endpoints`    | Row actions and form submit targets      |
 * | `system_architecture.components` | Dashboard system map                |
 * | `user_stories`              | User-flow walkthrough                    |
 * | `coverage_report`           | Dashboard donut                          |
 * | `implementation_plan.tasks` | Delivery checklist                       |
 * | `risk_register`             | Dashboard risk bars                      |
 * | `technology_decision`       | Stack panel                              |
 *
 * Where an artifact is missing the corresponding block is simply absent. A
 * project halfway through its lifecycle generates a smaller app, not a broken
 * one.
 */

import type { ArtifactDetail, ProjectDetail } from "@/lib/api";
import * as read from "@/lib/generation/extract";
import { sampleRows } from "@/lib/generation/sample-data";
import { deriveTheme } from "@/lib/generation/theme";
import type {
  AppSpec,
  Block,
  EntitySpec,
  FieldSpec,
  GeneratedPage,
  MetricSpec,
  NavItem,
  Provenance,
} from "@/lib/generation/types";

/** Index artifacts by type; the last of a type wins, matching lifecycle order. */
function byType(artifacts: ArtifactDetail[]): Map<string, ArtifactDetail> {
  const index = new Map<string, ArtifactDetail>();
  for (const artifact of artifacts) index.set(artifact.type, artifact);
  return index;
}

function provenance(rule: string, ...artifacts: Array<ArtifactDetail | undefined>): Provenance {
  return {
    rule,
    sourceArtifactIds: artifacts.filter((item): item is ArtifactDetail => Boolean(item)).map((item) => item.id),
  };
}

function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

/** Naive but adequate pluralisation for display labels. */
function pluralise(value: string): string {
  if (/[^aeiou]y$/i.test(value)) return `${value.slice(0, -1)}ies`;
  if (/(s|x|z|ch|sh)$/i.test(value)) return `${value}es`;
  return `${value}s`;
}

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/**
 * Storage type → form control.
 *
 * The schema artifact speaks in database terms (`timestamptz`, `uuid`, `bool`);
 * a form speaks in controls. This is the translation, and it is why a generated
 * form has date pickers and checkboxes rather than a wall of text inputs.
 */
function controlFor(type: string, name: string): FieldSpec["control"] {
  const storage = type.toLowerCase();
  const field = name.toLowerCase();

  if (/bool/.test(storage)) return "checkbox";
  if (/timestamp|datetime/.test(storage)) return "datetime";
  if (/date/.test(storage)) return "date";
  if (/int|numeric|decimal|float|double|money|serial/.test(storage)) return "number";
  if (/status|state|kind|category|role|type/.test(field)) return "select";
  if (/text$/.test(storage) && /(note|description|summary|comment|detail)/.test(field)) {
    return "textarea";
  }
  return "text";
}

/** Options for a `select`, inferred from the field's role. */
function optionsFor(name: string): string[] {
  const field = name.toLowerCase();
  if (field.includes("status") || field.includes("state")) {
    return ["Active", "Pending", "Scheduled", "Complete", "On hold"];
  }
  if (field.includes("role")) return ["Administrator", "Clinician", "Reception", "Billing"];
  if (field.includes("priority")) return ["Must", "Should", "Could"];
  return ["Option A", "Option B", "Option C"];
}

function toEntitySpec(entity: read.EntityLike, endpoints: read.EndpointLike[]): EntitySpec {
  // `id` columns are noise in a product UI: the user identifies a record by its
  // name, not its key. Kept out of the form, kept out of the leading column.
  const visible = entity.fields.filter((field) => field.name.toLowerCase() !== "id");
  const source = visible.length > 0 ? visible : entity.fields;

  const fields: FieldSpec[] = source.map((field, index) => ({
    name: field.name,
    label: titleCase(field.name),
    control: controlFor(field.type, field.name),
    required: !field.nullable,
    description: field.description,
    options: controlFor(field.type, field.name) === "select" ? optionsFor(field.name) : [],
    primary: index === 0,
  }));

  const noun = titleCase(entity.name);
  const related = endpoints.filter((endpoint) =>
    endpoint.path.toLowerCase().includes(slug(entity.name)),
  );

  return {
    name: noun,
    plural: pluralise(noun),
    purpose: entity.purpose,
    fields,
    relationships: entity.relationships,
    endpoints: related.map((endpoint) => ({
      method: endpoint.method,
      path: endpoint.path,
      purpose: endpoint.purpose,
    })),
    rows: sampleRows(entity.name, fields),
  };
}

export function synthesize(project: ProjectDetail, artifacts: ArtifactDetail[]): AppSpec {
  const index = byType(artifacts);
  const derivation: Provenance[] = [];
  const record = (item: Provenance) => {
    derivation.push(item);
    return item;
  };

  const prd = index.get("prd");
  const schema = index.get("database_schema");
  const contract = index.get("api_contract");
  const architecture = index.get("system_architecture");
  const stories = index.get("user_stories");
  const coverageArtifact = index.get("coverage_report");
  const plan = index.get("implementation_plan");
  const riskArtifact = index.get("risk_register");
  const techArtifact = index.get("technology_decision");

  const prdContent = read.contentOf(prd);
  const functional = read.requirements(prdContent, "functional_requirements");
  const nonFunctional = read.requirements(prdContent, "non_functional_requirements");
  const audiences = read.strList(prdContent.target_users);
  const objective = read.str(prdContent.objective, project.description);

  const endpoints = read.endpoints(read.contentOf(contract));
  const entitySpecs = read.entities(read.contentOf(schema)).map((entity) => toEntitySpec(entity, endpoints));
  const componentList = read.components(read.contentOf(architecture));
  const storyList = read.userStories(read.contentOf(stories));
  const cover = read.coverage(read.contentOf(coverageArtifact));
  const taskList = read.tasks(read.contentOf(plan));
  const riskList = read.risks(read.contentOf(riskArtifact));
  const choiceList = read.choices(read.contentOf(techArtifact));

  const pages: GeneratedPage[] = [];
  const nav: NavItem[] = [];

  // --- Landing ---------------------------------------------------------------
  const landingBlocks: Block[] = [
    {
      kind: "hero",
      headline: project.name,
      sub: objective,
      audiences,
      primaryAction: entitySpecs[0] ? `Open ${entitySpecs[0].plural}` : "Open the dashboard",
      provenance: record(provenance("prd.objective + prd.target_users → hero", prd)),
    },
  ];

  if (functional.length > 0) {
    landingBlocks.push({
      kind: "features",
      title: "What it does",
      items: functional.map((item) => ({
        id: item.id,
        title: item.title,
        description: item.description,
        priority: item.priority,
      })),
      provenance: record(provenance("prd.functional_requirements → feature cards", prd)),
    });
  }

  if (storyList.length > 0) {
    landingBlocks.push({
      kind: "flows",
      title: "How people use it",
      steps: storyList.map((story) => ({
        role: story.asA,
        wants: story.iWant,
        soThat: story.soThat,
        criteria: story.acceptanceCriteria,
      })),
      provenance: record(provenance("user_stories → user-flow walkthrough", stories)),
    });
  }

  if (choiceList.length > 0) {
    landingBlocks.push({
      kind: "stack",
      title: "Built with",
      items: choiceList.map((choice) => ({
        layer: choice.layer,
        choice: choice.choice,
        rationale: choice.rationale,
      })),
      provenance: record(provenance("technology_decision.choices → stack panel", techArtifact)),
    });
  }

  pages.push({
    id: "",
    title: "Overview",
    kind: "landing",
    description: objective,
    blocks: landingBlocks,
  });
  nav.push({ pageId: "", label: "Overview", icon: "Home" });

  // --- Dashboard -------------------------------------------------------------
  const metrics: MetricSpec[] = [];
  if (functional.length + nonFunctional.length > 0) {
    metrics.push({
      label: "Requirements",
      value: functional.length + nonFunctional.length,
      hint: `${functional.length} functional · ${nonFunctional.length} non-functional`,
      tone: "neutral",
    });
  }
  if (entitySpecs.length > 0) {
    metrics.push({
      label: "Data entities",
      value: entitySpecs.length,
      hint: `${entitySpecs.reduce((total, entity) => total + entity.fields.length, 0)} fields modelled`,
      tone: "neutral",
    });
  }
  if (endpoints.length > 0) {
    metrics.push({
      label: "API endpoints",
      value: endpoints.length,
      hint: "From the API contract",
      tone: "positive",
    });
  }
  if (cover.total > 0) {
    const percent = Math.round((cover.covered / cover.total) * 100);
    metrics.push({
      label: "Requirement coverage",
      value: percent,
      suffix: "%",
      hint: `${cover.covered} of ${cover.total} covered by tests`,
      tone: percent >= 80 ? "positive" : percent >= 50 ? "warning" : "critical",
    });
  }

  const dashboardBlocks: Block[] = [];
  if (metrics.length > 0) {
    dashboardBlocks.push({
      kind: "metrics",
      items: metrics,
      provenance: record(
        provenance("prd + database_schema + api_contract + coverage_report → metrics", prd, schema, contract, coverageArtifact),
      ),
    });
  }

  if (cover.total > 0) {
    dashboardBlocks.push({
      kind: "chart",
      title: "Requirement coverage",
      caption: "How much of the specification the test suite reaches.",
      variant: "donut",
      series: [
        { label: "Covered", value: cover.covered },
        { label: "Uncovered", value: Math.max(0, cover.total - cover.covered) },
      ],
      provenance: record(provenance("coverage_report → donut chart", coverageArtifact)),
    });
  }

  if (riskList.length > 0) {
    const weight: Record<string, number> = { low: 1, medium: 2, high: 3, critical: 4 };
    dashboardBlocks.push({
      kind: "chart",
      title: "Risk register",
      caption: "Impact of every risk the organization recorded.",
      variant: "bars",
      series: riskList.map((risk) => ({
        label: risk.description.slice(0, 42),
        value: weight[risk.impact.toLowerCase()] ?? 2,
      })),
      provenance: record(provenance("risk_register.risks → impact bars", riskArtifact)),
    });
  }

  if (componentList.length > 0) {
    dashboardBlocks.push({
      kind: "features",
      title: "System components",
      items: componentList.map((component, position) => ({
        id: `C-${position + 1}`,
        title: component.name,
        description:
          component.responsibility +
          (component.dependsOn.length > 0 ? ` Depends on ${component.dependsOn.join(", ")}.` : ""),
        priority: "component",
      })),
      provenance: record(provenance("system_architecture.components → system map", architecture)),
    });
  }

  if (taskList.length > 0) {
    dashboardBlocks.push({
      kind: "checklist",
      title: "Delivery plan",
      caption: "Tasks the implementation plan defines, in dependency order.",
      items: taskList.map((task) =>
        [task.id, task.title, task.estimate && `(${task.estimate})`].filter(Boolean).join(" · "),
      ),
      provenance: record(provenance("implementation_plan.tasks → delivery checklist", plan)),
    });
  }

  if (dashboardBlocks.length > 0) {
    pages.push({
      id: "dashboard",
      title: "Dashboard",
      kind: "dashboard",
      description: "Operational overview, derived from the engineering artifacts.",
      blocks: dashboardBlocks,
    });
    nav.push({ pageId: "dashboard", label: "Dashboard", icon: "LayoutDashboard" });
  }

  // --- One page per entity ---------------------------------------------------
  for (const entity of entitySpecs) {
    const pageId = slug(entity.plural);
    pages.push({
      id: pageId,
      title: entity.plural,
      kind: "entity",
      description: entity.purpose || `Manage ${entity.plural.toLowerCase()}.`,
      blocks: [
        {
          kind: "table",
          title: `All ${entity.plural.toLowerCase()}`,
          entity,
          provenance: record(
            provenance(`database_schema.entities[${entity.name}] → table`, schema, contract),
          ),
        },
        {
          kind: "form",
          title: `New ${entity.name.toLowerCase()}`,
          entity,
          submitLabel: `Create ${entity.name.toLowerCase()}`,
          provenance: record(
            provenance(`database_schema.entities[${entity.name}].fields → form controls`, schema),
          ),
        },
      ],
    });
    nav.push({ pageId, label: entity.plural, icon: "Table2" });
  }

  const theme = deriveTheme(`${project.name}:${project.id}`);
  const initials = project.name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]!.toUpperCase())
    .join("");

  return {
    brand: {
      name: project.name,
      tagline: objective,
      initials: initials || "AI",
    },
    theme,
    nav,
    pages,
    stats: {
      artifactsRead: artifacts.length,
      requirements: functional.length + nonFunctional.length,
      entities: entitySpecs.length,
      endpoints: endpoints.length,
      components: componentList.length,
      userStories: storyList.length,
      blocks: pages.reduce((total, page) => total + page.blocks.length, 0),
    },
    derivation,
  };
}
