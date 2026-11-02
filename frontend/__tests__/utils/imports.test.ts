import { describe, expect, test } from 'vitest';
import { confirmImport, describeCounts } from '../../utils/imports';

const counts = { created: 0, updated: 0, unchanged: 0, skipped: 0, error: 0 };

describe('describeCounts', () => {
  test('lists the non-zero counts', () => {
    expect(describeCounts({ ...counts, created: 2, updated: 1, error: 1 })).toBe(
      '2 new, 1 to update and 1 with errors',
    );
  });

  test('says when there is nothing to import', () => {
    expect(describeCounts(counts)).toBe('Nothing to import');
  });
});

describe('confirmImport', () => {
  test('names what will be created and updated', () => {
    expect(confirmImport({ ...counts, created: 2, updated: 1 }, 'customer', 'customers')).toBe(
      'Create 2 and update 1 customers?',
    );
    expect(confirmImport({ ...counts, created: 1 }, 'customer', 'customers')).toBe('Create 1 customer?');
  });
});
