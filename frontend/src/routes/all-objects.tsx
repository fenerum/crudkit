import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import CrudKitAPIClient from '../../data/api';

export default function AllObjects() {
  const client = new CrudKitAPIClient();

  const { data: apiRoot, isLoading: isRootLoading, error: rootError } = useQuery({
    queryKey: ['apiRoot'],
    queryFn: async () => {
      const response = await client.fetch('api/v1/');
      const data = await response.json();
      // Skip non-CRUD viewsets exposed by the DRF router. These don't have a
      // `/metadata/` action, so listing them here would 404.
      const NON_MODEL_ENDPOINTS = new Set(['search', 'schema', 'token', 'widgets']);
      return Object.keys(data).filter((key) => !NON_MODEL_ENDPOINTS.has(key));
    },
  });

  const { data: modelMetadata, isLoading: isMetadataLoading, error: metadataError } = useQuery({
    queryKey: ['allMetadata', apiRoot],
    queryFn: async () => {
      if (!apiRoot || apiRoot.length === 0) return {};
      const results = await Promise.all(
        apiRoot.map((modelType: string) =>
          client
            .metadata(modelType)
            .then((metadata) => ({ modelType, metadata }))
            .catch((error) => ({ modelType, error })),
        ),
      );
      return results.reduce<Record<string, any>>((acc, item: any) => {
        if (item.metadata) acc[item.modelType] = item.metadata;
        return acc;
      }, {});
    },
    enabled: !!apiRoot && apiRoot.length > 0,
  });

  const isLoading = isRootLoading || isMetadataLoading;
  const error = rootError || metadataError;

  if (isLoading) return <div className="p-4 text-fg-3 text-sm animate-pulse">Loading objects…</div>;
  if (error) return <div className="p-4 text-danger text-sm">Error: {(error as Error).message}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight text-fg-1">All objects</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {(apiRoot || []).map((modelType: string) => {
          const metadata = modelMetadata?.[modelType];
          if (!metadata) return null;
          return (
            <div
              key={modelType}
              className="rounded-md border border-border-1 bg-bg-2 overflow-hidden"
            >
              <div className="px-4 py-3 border-b border-border-1">
                <Link
                  to={`/${modelType}`}
                  className="text-base font-semibold text-fg-1 hover:text-primary-300"
                >
                  {metadata.verbose_name_plural || modelType}
                </Link>
              </div>
              <div className="px-4 py-3">
                <p className="text-xs text-fg-3">
                  {metadata.description || `${metadata.verbose_name || modelType} objects`}
                </p>
              </div>
              <div className="px-4 py-3 border-t border-border-1 flex items-center justify-between">
                <Link to={`/${modelType}`} className="text-xs text-primary-300 hover:text-primary-200">
                  Browse all
                </Link>
                <Link
                  to={`/${modelType}/create`}
                  className="text-xs text-primary-300 hover:text-primary-200"
                >
                  Create new
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
