import { vi, describe, beforeEach, test, expect } from 'vitest';

vi.mock('../../data/api', () => ({
  mergeObjects: vi.fn(),
  fetchObject: vi.fn(),
  fetchMetadata: vi.fn(),
}));

import { mergeObjects } from '../../data/api';

describe('Merge functionality', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mergeObjects.mockResolvedValue({ redirect: '/company/1' });
  });

  test('mergeObjects sends correct object IDs', async () => {
    const mergeData = {
      merge: ['1', '2'],
      id: '1',
      name: '1',
      email: '1',
    };

    await mergeObjects('company', mergeData);
    expect(mergeObjects).toHaveBeenCalledWith('company', mergeData);
  });

  test('mergeObjects sends only object IDs for values', async () => {
    const mergeData = {
      merge: ['1', '2'],
      id: '1',
      name: '2',
      email: '1',
    };

    await mergeObjects('company', mergeData);
    expect(mergeObjects).toHaveBeenCalledWith('company', {
      merge: ['1', '2'],
      id: '1',
      name: '2',
      email: '1',
    });
  });

  test('mergeObjects handles error cases', async () => {
    mergeObjects.mockRejectedValue(new Error('API error'));
    const mergeData = { merge: ['1', '2'], id: '1' };
    await expect(mergeObjects('company', mergeData)).rejects.toThrow('API error');
  });

  test('handles filtering of non-editable fields from metadata', async () => {
    const mockMetadata = {
      fields: {
        id: { editable: false },
        name: { editable: true },
        created_at: { editable: false },
        label: { editable: true },
      },
    };

    const mockSelectedValues = {
      id: '1',
      name: '2',
      created_at: '1',
      label: '2',
      non_existent: '1',
    };

    const filteredMergeData = {
      merge: ['1', '2'],
      ...Object.entries(mockSelectedValues).reduce((acc, [field, objectId]) => {
        if (mockMetadata.fields[field] && (mockMetadata.fields[field].editable || field === 'id')) {
          acc[field] = objectId;
        }
        return acc;
      }, {}),
    };

    await mergeObjects('company', filteredMergeData);

    expect(mergeObjects).toHaveBeenCalledWith('company', {
      merge: ['1', '2'],
      id: '1',
      name: '2',
      label: '2',
    });

    const mergeCall = mergeObjects.mock.calls[0][1];
    expect(mergeCall).not.toHaveProperty('created_at');
    expect(mergeCall).not.toHaveProperty('non_existent');
  });
});
