import { describe, expect, test } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { invalidateChangedModels } from '../../data/realtime';

function staleKeys(qc: QueryClient) {
  return qc
    .getQueryCache()
    .getAll()
    .filter((q) => q.state.isInvalidated)
    .map((q) => JSON.stringify(q.queryKey))
    .sort();
}

describe('invalidateChangedModels', () => {
  test('invalidates the changed model and its dependents only', () => {
    const qc = new QueryClient();
    const keys = [
      ['list', 'WLG', {}],
      ['detail', 'WLG', 'WLG1'],
      ['inline-count', 'WLG', 'RDG1'],
      ['activeWorkLog', 1],
      ['view', 'RDG', 'VIW1', 1],
      ['widgets'],
      ['list', 'RDG', {}],
      ['detail', 'RDG', 'RDG1'],
    ];
    keys.forEach((key) => qc.setQueryData(key, {}));

    invalidateChangedModels(qc, ['WLG']);

    expect(staleKeys(qc)).toEqual(
      [
        ['activeWorkLog', 1],
        ['detail', 'WLG', 'WLG1'],
        ['inline-count', 'WLG', 'RDG1'],
        ['list', 'WLG', {}],
        ['widgets'],
      ]
        .map((k) => JSON.stringify(k))
        .sort(),
    );
  });

  test('a view change refreshes saved-view queries of every model', () => {
    const qc = new QueryClient();
    qc.setQueryData(['view', 'RDG', 'VIW1', 1], {});
    qc.setQueryData(['views', 'RDG'], {});
    qc.setQueryData(['layouts', 'RDG'], {});
    invalidateChangedModels(qc, ['VIW']);
    expect(staleKeys(qc)).toEqual([JSON.stringify(['view', 'RDG', 'VIW1', 1]), JSON.stringify(['views', 'RDG'])]);
  });

  test('a layout change refreshes layout queries of every model', () => {
    const qc = new QueryClient();
    qc.setQueryData(['layouts', 'RDG'], {});
    qc.setQueryData(['views', 'RDG'], {});
    invalidateChangedModels(qc, ['LAY']);
    expect(staleKeys(qc)).toEqual([JSON.stringify(['layouts', 'RDG'])]);
  });
});
