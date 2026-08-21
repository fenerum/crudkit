import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import CrudKitAPIClient from '../data/api';

// Shared menu data with a single query key per model so that
// `invalidateModel(qc, 'VIW')` / `invalidateModel(qc, 'WSP')` (which
// prefix-match ['list', model]) refresh every menu consumer: sidebar,
// command palette, and dashboard.
function useMenuList(model, options = {}) {
  const client = useMemo(() => new CrudKitAPIClient(), []);
  const { isPending, error, data } = useQuery({
    queryKey: ['list', model, {}],
    queryFn: () => client.list(model, { page_size: 500 }),
    ...options,
  });
  const items = data?.isPaginated ? data.results : data;
  return { isPending, error, items: items || [] };
}

// All saved views, unfiltered — workspace tabs may pin views with
// show_in_menu=False, so consumers that only want pinned views filter
// `show_in_menu` client-side.
export function useMenuViews(options = {}) {
  return useMenuList('VIW', options);
}

export function useWorkspaces(options = {}) {
  return useMenuList('WSP', options);
}
