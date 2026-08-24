export function listQueryKey(
  type: string,
  viewId: string | undefined,
  page: number,
  query: string,
  pageSize: number | null,
  filters: Record<string, string>,
) {
  const normalizedFilters = Object.fromEntries(Object.entries(filters).sort(([left], [right]) => left.localeCompare(right)));
  return ['list', type, viewId, page, query, pageSize, normalizedFilters] as const;
}
