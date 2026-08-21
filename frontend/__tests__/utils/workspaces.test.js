import { describe, expect, test } from 'vitest';
import { resolveWorkspaceViews } from '../../utils/workspaces';

const views = [
  { id: 'VIW1', name: 'Leads' },
  { id: 'VIW2', name: 'Won deals' },
  { id: 'VIW3', name: 'My tasks' },
];

describe('resolveWorkspaceViews', () => {
  test('resolves views in workspace order', () => {
    const workspace = { views: ['VIW3', 'VIW1'] };
    expect(resolveWorkspaceViews(workspace, views).map((v) => v.name)).toEqual([
      'My tasks',
      'Leads',
    ]);
  });

  test('skips missing/deleted view ids', () => {
    const workspace = { views: ['VIW9', 'VIW2'] };
    expect(resolveWorkspaceViews(workspace, views).map((v) => v.id)).toEqual(['VIW2']);
  });

  test('skips duplicate ids, keeping the first occurrence', () => {
    const workspace = { views: ['VIW1', 'VIW2', 'VIW1'] };
    expect(resolveWorkspaceViews(workspace, views).map((v) => v.id)).toEqual(['VIW1', 'VIW2']);
  });

  test.each([
    ['null workspace', null, views],
    ['non-array views', { views: 'VIW1' }, views],
    ['missing views key', {}, views],
    ['non-array allViews', { views: ['VIW1'] }, null],
  ])('returns [] for %s', (_label, workspace, allViews) => {
    expect(resolveWorkspaceViews(workspace, allViews)).toEqual([]);
  });

  test('empty views list resolves to []', () => {
    expect(resolveWorkspaceViews({ views: [] }, views)).toEqual([]);
  });
});
