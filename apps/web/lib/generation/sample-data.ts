/**
 * Plausible sample rows for a generated entity.
 *
 * A generated table with no rows in it demonstrates nothing — the whole point is
 * to show what the product would look like in use. So rows are synthesised from
 * the entity's own field names and storage types.
 *
 * Deterministic on purpose: the same schema always yields the same rows, so a
 * screenshot stays valid and two people demoing the same project see the same
 * screen. Values are obviously illustrative (no real-looking patient names), and
 * the UI labels them as sample data — a generated preview must never be
 * mistakeable for real records.
 */

import type { FieldSpec } from "@/lib/generation/types";

function seeded(seed: string, index: number): number {
  let value = 0x811c9dc5 ^ index;
  for (let position = 0; position < seed.length; position += 1) {
    value ^= seed.charCodeAt(position);
    value = Math.imul(value, 0x01000193) >>> 0;
  }
  return value;
}

const STATUSES = ["Active", "Pending", "Scheduled", "Complete", "On hold"];
const NAMES = ["Alder", "Brookes", "Castellan", "Devi", "Ellison", "Farrow", "Gable", "Haldane"];
const CITIES = ["Northgate", "Riverside", "Eastfield", "Westmoor", "Southbank"];

/**
 * Map a field to a value that looks like what that field would hold.
 *
 * Keyed off the field *name* first and the storage type second, because
 * "status" holding "Active" reads as a real product while "status" holding
 * "text-3" reads as scaffolding.
 */
function valueFor(field: FieldSpec, seed: string, row: number): string | number | boolean {
  const random = seeded(`${seed}:${field.name}`, row);
  const name = field.name.toLowerCase();

  if (field.control === "checkbox") return random % 3 !== 0;
  if (field.control === "select" && field.options.length > 0) {
    return field.options[random % field.options.length]!;
  }

  if (field.control === "date" || field.control === "datetime") {
    const day = (random % 26) + 1;
    const month = (random >> 4) % 12;
    const date = new Date(Date.UTC(2026, month, day, 9 + (random % 8), (random % 4) * 15));
    return field.control === "date"
      ? date.toISOString().slice(0, 10)
      : date.toISOString().slice(0, 16).replace("T", " ");
  }

  if (field.control === "number") {
    if (name.includes("price") || name.includes("amount") || name.includes("total")) {
      return Number(((random % 90_000) / 100 + 20).toFixed(2));
    }
    return random % 500;
  }

  if (name.includes("status") || name.includes("state")) return STATUSES[random % STATUSES.length]!;
  if (name.includes("email")) {
    return `${NAMES[random % NAMES.length]!.toLowerCase()}@example.org`;
  }
  if (name.includes("phone")) return `+1 555 0${100 + (random % 899)}`;
  if (name.includes("city") || name.includes("location") || name.includes("address")) {
    return CITIES[random % CITIES.length]!;
  }
  if (name.includes("name") || name.includes("title") || name.includes("label")) {
    return NAMES[random % NAMES.length]!;
  }
  if (name === "id" || name.endsWith("_id")) {
    return `${field.name.replace(/_id$/, "").slice(0, 3).toUpperCase()}-${1000 + (random % 8999)}`;
  }

  return `${NAMES[random % NAMES.length]!} ${(random % 90) + 10}`;
}

export function sampleRows(
  entityName: string,
  fields: FieldSpec[],
  count = 6,
): Array<Record<string, string | number | boolean>> {
  if (fields.length === 0) return [];

  return Array.from({ length: count }, (_, row) => {
    const record: Record<string, string | number | boolean> = {};
    for (const field of fields) {
      record[field.name] = valueFor(field, entityName, row);
    }
    return record;
  });
}
