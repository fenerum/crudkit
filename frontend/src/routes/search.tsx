import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import CrudKitAPIClient from '../../data/api';
import { isObjectTypeCode } from '../../utils/crudkit';
import { detail as detailRegex } from '../../utils/urls';

export default function SearchPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const client = useMemo(() => new CrudKitAPIClient(), []);
  const [directMatch, setDirectMatch] = useState<any>(null);

  const isTypeCode = useMemo(
    () => searchQuery && isObjectTypeCode(searchQuery.toUpperCase()),
    [searchQuery],
  );

  const typeMetadataQuery = useQuery({
    queryKey: ['metadata', searchQuery],
    queryFn: async () => {
      try {
        return await client.metadata(searchQuery.toUpperCase());
      } catch {
        return null;
      }
    },
    enabled: Boolean(isTypeCode),
    retry: false,
    staleTime: 60_000,
  });

  const objectTypeMatch = useMemo(() => {
    if (isTypeCode && typeMetadataQuery.data) {
      return {
        type: searchQuery.toUpperCase(),
        name:
          typeMetadataQuery.data.verbose_name_plural ||
          typeMetadataQuery.data.verbose_name ||
          searchQuery.toUpperCase(),
      };
    }
    return null;
  }, [isTypeCode, searchQuery, typeMetadataQuery.data]);

  useEffect(() => {
    setDirectMatch(null);
    if (searchQuery && detailRegex.test(searchQuery.toUpperCase())) {
      const id = searchQuery.toUpperCase();
      const modelType = id.slice(0, 3);
      (async () => {
        try {
          const response = await client.retrieve(modelType, id);
          if (response) {
            setDirectMatch({
              id,
              type: modelType,
              label: response.label || response.object_repr || id,
            });
          }
        } catch (error) {
          console.error('Object fetch error:', error);
        }
      })();
    }
  }, [searchQuery, client]);

  const searchResults = useQuery({
    queryKey: ['search', searchQuery],
    queryFn: async () => {
      if (!searchQuery || searchQuery.length < 2) return [];
      if (directMatch || objectTypeMatch) return [];
      const data = await client.search(searchQuery);
      return data.results || [];
    },
    enabled: searchQuery.length >= 2 && !directMatch && !objectTypeMatch,
  });

  return (
    <div className="space-y-4">
      <div>
        <input
          type="text"
          placeholder="Search anything…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          autoCapitalize="off"
          autoComplete="off"
          autoCorrect="off"
          className="ck-input w-full max-w-xl"
          autoFocus
        />
      </div>

      {(directMatch || objectTypeMatch) && (
        <div>
          <div className="eyebrow mb-2">Quick access</div>
          {directMatch && (
            <Link
              to={`/${directMatch.id}`}
              className="block rounded-md border border-success/30 bg-bg-2 px-4 py-3 hover:bg-bg-3"
            >
              <div className="text-sm font-semibold text-fg-1">{directMatch.label}</div>
              <div className="text-xs text-fg-3 mt-0.5">
                {directMatch.id} · Go to this {directMatch.type.toLowerCase()} directly
              </div>
            </Link>
          )}
          {objectTypeMatch && !directMatch && (
            <Link
              to={`/${objectTypeMatch.type}`}
              className="block rounded-md border border-border-1 bg-bg-2 px-4 py-3 hover:bg-bg-3"
            >
              <div className="text-sm font-semibold text-fg-1">{objectTypeMatch.name}</div>
              <div className="text-xs text-fg-3 mt-0.5">
                View all {objectTypeMatch.name.toLowerCase()}
              </div>
            </Link>
          )}
        </div>
      )}

      {!directMatch && !objectTypeMatch && searchResults.isFetching && (
        <div className="text-sm text-fg-3 animate-pulse">Searching…</div>
      )}

      {!directMatch &&
        !objectTypeMatch &&
        searchQuery.length >= 2 &&
        !searchResults.isFetching &&
        (searchResults.data || []).length === 0 && (
          <div className="text-sm text-fg-3">No results for &quot;{searchQuery}&quot;</div>
        )}

      {!directMatch && !objectTypeMatch && (searchResults.data || []).length > 0 && (
        <ul className="divide-y divide-border-1 rounded-md border border-border-1 bg-bg-2">
          {(searchResults.data as any[]).map((item) => (
            <li key={item.id}>
              <Link to={`/${item.id}`} className="block px-4 py-3 hover:bg-bg-3">
                <div className="text-sm font-semibold text-fg-1">{item.label}</div>
                <div className="text-xs text-fg-3 mt-0.5">
                  {item.id}
                  {item.description ? ` · ${item.description}` : ''}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
