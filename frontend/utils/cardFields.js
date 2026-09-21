// Heuristics for picking interesting fields off an object so kanban / swimlane
// cards can render a consistent layout (priority, amount) without the caller
// having to know which field on which model carries each piece of info.

import { choiceLabel } from './choices';

export const PRIORITY_FIELDS = ['priority', 'severity', 'importance'];
export const AMOUNT_FIELDS = ['amount', 'value', 'price', 'mrr', 'arr', 'total'];

export function findFieldByNames(object, names) {
  if (!object) return null;
  return Object.keys(object).find(k =>
    names.includes(k.toLowerCase()) && object[k] !== null && object[k] !== undefined
  );
}

export function priorityLevel(value) {
  if (value == null) return null;
  const v = typeof value === 'object' && value?.label ? value.label : value;
  if (typeof v === 'number') return Math.max(1, Math.min(4, v));
  if (typeof v !== 'string') return null;
  const s = v.toLowerCase();
  if (/(urgent|critical)/.test(s)) return 4;
  if (/high/.test(s)) return 3;
  if (/(medium|normal)/.test(s)) return 2;
  if (/low/.test(s)) return 1;
  return null;
}

// Level + accessible label ("priority: High") for the PriorityBars badge.
export function priorityBadge(object, metadata) {
  const field = findFieldByNames(object, PRIORITY_FIELDS);
  const level = priorityLevel(field ? object[field] : null);
  if (level == null) return null;
  const meta = metadata.fields[field];
  const label = meta ? `${meta.verbose_name}: ${choiceLabel(meta, object[field])}` : undefined;
  return { field, level, label };
}
