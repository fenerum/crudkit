import * as React from 'react';
import Badge from './Badge';
import { hashName } from './avatarPalette';

const STAGE_HUES = [
  'var(--stage-slate)',
  'var(--stage-blue)',
  'var(--stage-violet)',
  'var(--stage-amber)',
  'var(--stage-green)',
  'var(--stage-rose)',
];

// Won/Lost/Closed words map to semantic hues; unknown values get a deterministic
// hue from the stage palette so distinct values look distinct without metadata.
function colorForStage(value, color) {
  if (color) return color;
  const v = String(value || '').toLowerCase();
  if (!v) return STAGE_HUES[0];
  if (/won|success|active|paid/.test(v))           return 'var(--success)';
  if (/lost|cancel|fail|expired|delete/.test(v))   return 'var(--danger)';
  if (/negotiat|warn|pending|review/.test(v))      return 'var(--warn)';
  if (/lead|new|draft/.test(v))                    return 'var(--stage-slate)';
  if (/qualif|info/.test(v))                       return 'var(--stage-blue)';
  if (/proposal/.test(v))                          return 'var(--stage-violet)';
  return STAGE_HUES[hashName(v) % STAGE_HUES.length];
}

export default function StageBadge({ value, label, color }) {
  const dot = colorForStage(value, color);
  return <Badge dot={dot}>{label || value || '—'}</Badge>;
}

export { colorForStage };
