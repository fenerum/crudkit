// Saved-view filters are stored as `[[field, comparator, value], ...]` and
// ANDed together by `View.filter` on the backend.

export const COMPARATORS = ["=", "!=", ">", ">=", "<", "<="];
export const ORDERING_COMPARATORS = [">", ">=", "<", "<="];

// Mirrors `resolve_variable_value` in backend/src/crudkit/utils.py.
export const FILTER_VARIABLES = [{ value: "${user}", label: "Current user" }];

export type FieldKind = "choice" | "boolean" | "number" | "date" | "datetime" | "fk" | "text" | "path";

type FieldMeta = {
  type?: string;
  choices?: [unknown, string][] | null;
  related_model?: string | null;
  related_model_type?: string | null;
  verbose_name?: string;
};

export function isVariable(value: unknown) {
  return FILTER_VARIABLES.some((v) => v.value === value);
}

export function fieldKind(meta: FieldMeta | undefined): FieldKind {
  if (!meta) return "path";
  if (meta.choices) return "choice";
  const type = meta.type || "";
  if (/BooleanField$/.test(type)) return "boolean";
  if (meta.related_model_type) return "fk";
  if (/(Integer|Decimal|Float|Money|Auto)Field$/.test(type) || meta.related_model) return "number";
  if (type === "DateField") return "date";
  if (/DateTimeField$/.test(type)) return "datetime";
  return "text";
}

export function supportsOrdering(kind: FieldKind) {
  return kind === "number" || kind === "date" || kind === "datetime" || kind === "path";
}

// Returns the rows to edit, or `{ raw }` when the stored value can't be read
// as a list at all (the editor then shows it as text for the user to fix).
export function parseFilters(value: unknown): { rows: unknown[] } | { raw: string } {
  if (value == null || value === "") return { rows: [] };
  let parsed = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return { raw: value };
    }
  }
  if (!Array.isArray(parsed)) return { raw: JSON.stringify(parsed, null, 2) };
  return { rows: parsed };
}

export function isTriple(row: unknown): row is [string, string, unknown] {
  return Array.isArray(row) && row.length === 3 && typeof row[0] === "string" && typeof row[1] === "string";
}

const CK_ID = /^[A-Z]{3}[0-9]+$/;

// The CK-ID of the record an FK filter value points at; plain pks are
// accepted too since the backend's CrudKitIDField takes either.
export function fkCkId(value: unknown, relatedType: string): string | null {
  if (typeof value === "string" && CK_ID.test(value)) return value;
  if (isNumeric(value) && Number.isInteger(Number(value))) return `${relatedType}${value}`;
  return null;
}

export function isNumeric(value: unknown) {
  if (typeof value === "number") return Number.isFinite(value);
  return typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value));
}

function isDate(value: unknown, pattern: RegExp) {
  return typeof value === "string" && pattern.test(value) && !isNaN(Date.parse(value));
}

function valueError(kind: FieldKind, meta: FieldMeta, value: unknown): string | null {
  if (value === null || isVariable(value)) return null;
  const shown = JSON.stringify(value);
  switch (kind) {
    case "choice":
      return meta.choices!.some(([choice]) => String(choice) === String(value))
        ? null
        : `${shown} is not one of the choices`;
    case "boolean":
      return typeof value === "boolean" ? null : `${shown} is not yes or no`;
    case "number":
      return isNumeric(value) ? null : `${shown} is not a number`;
    case "fk":
      return fkCkId(value, meta.related_model_type!) ? null : `${shown} is not a record ID`;
    case "date":
      return isDate(value, /^\d{4}-\d{2}-\d{2}$/) ? null : `${shown} is not a date`;
    case "datetime":
      return isDate(value, /^\d{4}-\d{2}-\d{2}/) ? null : `${shown} is not a date and time`;
    default:
      return null;
  }
}

// `null` when the row is a usable filter, otherwise a message for the user.
export function validateFilter(row: unknown, fieldMetaByName: Record<string, FieldMeta>): string | null {
  if (!isTriple(row)) return `Not a [field, comparator, value] filter: ${JSON.stringify(row)}`;
  const [field, comparator, value] = row;
  const meta = fieldMetaByName[field];
  if (!field) return "Pick a field";
  if (!meta && !field.includes("__")) return `Unknown field "${field}"`;
  if (!COMPARATORS.includes(comparator)) return `Unknown comparator "${comparator}"`;
  return meta ? valueError(fieldKind(meta), meta, value) : null;
}
