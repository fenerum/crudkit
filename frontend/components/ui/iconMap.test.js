import { hasIcon } from './iconMap';
import path from 'node:path';
import { readFileSync } from 'node:fs';

// The backend offers these icons in its IconField dropdown; each must be one the SPA can draw.
test('every icon the backend offers can be drawn', () => {
  const fields = readFileSync(path.join(import.meta.dirname, '../../../backend/src/crudkit/fields.py'), 'utf8');
  const names = [...fields.match(/ICON_NAMES = \(([^)]*)\)/)[1].matchAll(/"([a-z0-9-]+)"/g)].map((m) => m[1]);
  expect(names.length).toBeGreaterThan(10);
  expect(names.filter((name) => !hasIcon(name))).toEqual([]);
});
