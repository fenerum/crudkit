// Dependent fields: a field's `depends_on` (from the metadata endpoint) says when
// it applies, whether it is required then, which choices fit another field, and
// which linked records match. The backend enforces the same rules on save
// (crudkit.dependencies); this mirrors them while a form is being filled in.

export interface DependsOn {
  when?: Record<string, string[]> | null;
  required?: boolean;
  options_from?: string | null;
  options?: Record<string, string[]> | null;
  match?: Record<string, string> | null;
}

type FieldMeta = { depends_on?: DependsOn | null; choices?: [any, string][] | null; [key: string]: any };
type Metadata = Record<string, any>;

/** A value as the rules compare it: records by ID, booleans as true/false, the rest as text. */
export function ruleKey(value: any): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "object" && "id" in value) return ruleKey(value.id);
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

/** Whether the field governed by `rule` applies, given the record's current `values`. */
export function applies(rule: DependsOn | null | undefined, values: Record<string, any>): boolean {
  if (!rule?.when) return true;
  return Object.entries(rule.when).every(([name, allowed]) => allowed.includes(ruleKey(values?.[name]) as string));
}

/** The choices of a field allowed while `values` hold, or null when every choice is. */
export function allowedChoices(rule: DependsOn | null | undefined, values: Record<string, any>): string[] | null {
  if (!rule?.options_from || !rule.options) return null;
  const controlling = ruleKey(values?.[rule.options_from]);
  if (controlling === null) return null;
  return rule.options[controlling] ?? null;
}

/** The list filters a linked-record picker should apply, e.g. {customer: "CUS1"}. */
export function matchFilter(rule: DependsOn | null | undefined, values: Record<string, any>): Record<string, string> | null {
  if (!rule?.match) return null;
  const filter: Record<string, string> = {};
  for (const [linkedField, ownField] of Object.entries(rule.match)) {
    const own = ruleKey(values?.[ownField]);
    if (own !== null) filter[linkedField] = own;
  }
  return Object.keys(filter).length ? filter : null;
}

/**
 * The metadata of each field as it stands for `values`: fields that don't apply
 * are listed in `hidden`, required ones say so, choices are narrowed, and pickers
 * get `list_filter`. Fields without rules are passed through unchanged.
 */
export function resolveMetadata(metadata: Metadata, values: Record<string, any>) {
  const hidden = new Set<string>();
  const resolved: Metadata = {};
  for (const [name, meta] of Object.entries(metadata || {})) {
    const rule = meta?.depends_on;
    if (!meta || !rule) {
      resolved[name] = meta;
      continue;
    }
    if (!applies(rule, values)) {
      hidden.add(name);
      resolved[name] = meta;
      continue;
    }
    const next: FieldMeta = { ...meta };
    if (rule.required) next.required = true;
    const allowed = allowedChoices(rule, values);
    if (allowed && Array.isArray(meta.choices)) {
      next.choices = meta.choices.filter(([value]) => allowed.includes(String(value)));
    }
    const filter = matchFilter(rule, values);
    if (filter) next.list_filter = filter;
    resolved[name] = next;
  }
  return { metadata: resolved, hidden };
}
