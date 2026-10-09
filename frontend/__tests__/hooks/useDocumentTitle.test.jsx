import { beforeEach, describe, expect, test, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../data/api', () => ({
  default: vi.fn(),
  fetchMetadata: vi.fn(),
  fetchObject: vi.fn(),
  fetchObjects: vi.fn(),
}));

import { fetchMetadata, fetchObject, fetchObjects } from '../../data/api';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

function renderAt(path) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  renderHook(() => useDocumentTitle('CRM'), { wrapper });
}

describe('useDocumentTitle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMetadata.mockResolvedValue({ verbose_name_plural: 'opportunities' });
    fetchObjects.mockResolvedValue({ count: 2, results: [] });
  });

  test('uses the view name for a view without a badge', async () => {
    fetchObject.mockResolvedValue({ id: 5, model: 'OPP', name: 'All Opportunities', show_badge_in_menu: false });
    renderAt('/OPP/VIW/VIW5');
    await waitFor(() => expect(document.title).toBe('All Opportunities - CRM'));
    expect(fetchObjects).not.toHaveBeenCalled();
  });

  test('prefixes the badge count for a badged view', async () => {
    fetchObject.mockResolvedValue({ id: 6, model: 'OPP', name: 'Open Opportunities', show_badge_in_menu: true, filters: null });
    renderAt('/OPP/VIW/VIW6');
    await waitFor(() => expect(document.title).toBe('(2) Open Opportunities - CRM'));
    expect(fetchObjects).toHaveBeenCalledWith('OPP', { page_size: 1, _fields: 'id', _view: 6 });
  });

  test('uses the verbose plural on a model list', async () => {
    renderAt('/OPP');
    await waitFor(() => expect(document.title).toBe('Opportunities - CRM'));
  });
});
