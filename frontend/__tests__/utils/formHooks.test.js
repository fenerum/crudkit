import { beforeEach, describe, expect, test } from 'vitest';
import CrudKitAPIClient, { ValidationError } from '../../data/api';

describe('CrudKitAPIClient.cleanObject', () => {
  let apiClient;
  let mockMetadata;

  beforeEach(() => {
    mockMetadata = {
      fields: {
        name: { type: 'CharField', editable: true },
        is_active: { type: 'BooleanField', editable: true },
        knowledge_base: { type: 'ForeignKey', related_model: 'KNB', editable: true },
        owner: { type: 'ForeignKey', related_model: 'USR', editable: true },
      },
    };
    apiClient = new CrudKitAPIClient();
  });

  test('extracts ID from foreign key objects', () => {
    const formData = {
      name: 'Test Article',
      is_active: true,
      knowledge_base: { id: 'KNB1', label: 'Test', name: 'Test KB' },
    };

    const result = apiClient.cleanObject(mockMetadata, formData);
    expect(result.knowledge_base).toBe('KNB1');
    expect(result.name).toBe('Test Article');
    expect(result.is_active).toBe(true);
  });

  test('leaves primitive foreign key values unchanged', () => {
    const formData = { name: 'Test Article', knowledge_base: 'KNB1' };
    const result = apiClient.cleanObject(mockMetadata, formData);
    expect(result.knowledge_base).toBe('KNB1');
  });

  test('coerces missing booleans to false', () => {
    const formData = { name: 'Test', is_active: undefined };
    const result = apiClient.cleanObject(mockMetadata, formData);
    expect(result.is_active).toBe(false);
  });

  test('coerces "on" to true for booleans (HTML form values)', () => {
    const formData = { name: 'Test', is_active: 'on' };
    const result = apiClient.cleanObject(mockMetadata, formData);
    expect(result.is_active).toBe(true);
  });

  test('throws ValidationError on bad JSON', () => {
    const metaWithJson = {
      fields: {
        ...mockMetadata.fields,
        config: { type: 'JSONField', editable: true },
      },
    };
    expect(() => apiClient.cleanObject(metaWithJson, { config: '{not json' })).toThrow(
      ValidationError,
    );
  });
});
