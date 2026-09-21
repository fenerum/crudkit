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

// Only views with show_in_menu ever appear in a menu, including workspace tabs.
export function useMenuViews(options = {}) {
  const { items, ...rest } = useMenuList('VIW', options);
  const menuViews = useMemo(() => items.filter((v) => v.show_in_menu), [items]);
  return { ...rest, items: menuViews };
}

export function useWorkspaces(options = {}) {
  return useMenuList('WSP', options);
}

export function isMine(item, userId) {
  const owner = typeof item.created_by === 'object' ? item.created_by?.id : item.created_by;
  return owner != null && userId != null && String(owner) === String(userId);
}

// The API returns every view/workspace to superusers; only surface public
// ones plus the current user's own private ones.
export function isVisibleToUser(item, userId) {
  return item.public || isMine(item, userId);
}
