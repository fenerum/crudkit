import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'react-toastify';
import CrudKitAPIClient, { fetchObject } from '../../data/api';
import { useMetadata } from '../../utils/formHooks';
import { url } from '../../utils/urls';
import ReadOnlyField from '../../components/ReadOnlyField';

export default function Merge() {
  const { segment } = useParams() as { segment: string };
  const [searchParams] = useSearchParams();
  const objectIds = searchParams.getAll('object_id');
  const navigate = useNavigate();

  const [objects, setObjects] = useState<any[]>([]);
  const [selectedValues, setSelectedValues] = useState<Record<string, any>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const client = new CrudKitAPIClient();
  const { metadata, isMetadataLoading, metadataError } = useMetadata(segment);

  const mergeMutation = useMutation({
    mutationFn: (mergeData: any) => {
      const id = mergeData.merge[0];
      return client.merge(segment, id, mergeData);
    },
    onSuccess: (response: any) => {
      if (response.messages && response.messages.length > 0) {
        response.messages.forEach((m: string) => toast.success(m));
      } else {
        toast.success('Objects merged successfully');
      }
      if (response.redirect) {
        if (response.redirect.startsWith('http')) {
          window.location.href = response.redirect;
        } else if (response.redirect.startsWith('/')) {
          navigate(response.redirect, { replace: true });
        } else {
          navigate(url(response.redirect), { replace: true });
        }
      } else {
        navigate(-1);
      }
    },
    onError: (err: any) => {
      console.error('Merge error:', err);
      if (err.errors && Array.isArray(err.errors)) {
        err.errors.forEach((m: string) => toast.error(m));
        setError(err.errors[0] || 'Merge operation failed');
      } else {
        toast.error('Failed to merge objects: ' + (err.message || 'Unknown error'));
        setError('Failed to merge objects: ' + (err.message || 'Unknown error'));
      }
    },
  });

  useEffect(() => {
    const load = async () => {
      if (!objectIds.length) {
        setError('No objects specified for merging');
        setIsLoading(false);
        return;
      }
      try {
        const fetched = await Promise.all(objectIds.map((id) => fetchObject(segment, id)));
        setObjects(fetched);
        setIsLoading(false);
      } catch (err) {
        console.error('Error loading objects for merge:', err);
        setError('Failed to load objects');
        setIsLoading(false);
      }
    };
    load();
    // objectIds is recomputed each render; serialize for the dep.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segment, objectIds.join(',')]);

  useEffect(() => {
    if (metadata && objects.length > 0) {
      const initial: Record<string, any> = {};
      Object.keys(objects[0]).forEach((field) => {
        if (metadata.fields[field] && (metadata.fields[field].editable || field === 'id')) {
          let chosen = objects[0].id;
          if (objects[0][field] === null) {
            const withValue = objects.find((o) => o[field] !== null);
            if (withValue) chosen = withValue.id;
          }
          initial[field] = chosen;
        }
      });
      setSelectedValues(initial);
    }
  }, [metadata, objects]);

  const handleMerge = () => {
    if (!objects.length) return;
    setError(null);
    const mergeData = {
      merge: objects.map((o) => o.id),
      ...Object.entries(selectedValues).reduce<Record<string, any>>((acc, [field, objectId]) => {
        if (metadata?.fields[field] && (metadata.fields[field].editable || field === 'id')) {
          acc[field] = objectId;
        }
        return acc;
      }, {}),
    };
    return mergeMutation.mutateAsync(mergeData);
  };

  if (isLoading || isMetadataLoading) return <div className="p-4 text-fg-3 text-sm">Loading…</div>;

  if (error || metadataError) {
    return (
      <div className="p-4">
        <div
          className="flex items-start gap-2.5 rounded-md border bg-bg-2 px-3.5 py-2.5 mb-4"
          style={{ borderColor: 'var(--danger)' }}
        >
          <span className="flex-shrink-0 mt-0.5" style={{ color: 'var(--danger)' }}>
            !
          </span>
          <div className="flex-1 text-sm" style={{ color: 'var(--danger)' }}>
            <div className="font-semibold">Error</div>
            <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">
              {error || (metadataError as Error)?.message}
            </pre>
          </div>
        </div>
        <button type="button" onClick={() => navigate(-1)} className="ck-btn ck-btn-secondary ck-btn-sm">
          Go back
        </button>
      </div>
    );
  }

  if (!objects.length) return <div className="p-4 text-fg-3 text-sm">No objects to merge</div>;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-base font-semibold text-fg-1 tracking-tight">
          Merge {objects.length} records
        </h2>
        <p className="text-xs text-fg-3 mt-1">
          Select which values to keep for each field. The other records will be deleted.
        </p>
      </div>

      <div className="overflow-hidden rounded-md border border-border-1 bg-bg-1">
        <div className="overflow-x-auto">
          <table className="min-w-full" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr className="bg-bg-2 border-b border-border-1">
                <th className="px-4 py-2 text-left eyebrow">Field</th>
                {objects.map((object, index) => (
                  <th key={object.id} className="px-4 py-2 text-left eyebrow">
                    Record {index + 1}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metadata &&
                Object.entries(metadata.fields)
                  .filter(([field, fieldMeta]: any) => fieldMeta.editable || field === 'id')
                  .map(([field, fieldMeta]: any) => (
                    <tr key={field} className="border-b border-border-1 last:border-b-0">
                      <td className="px-4 py-2 text-sm font-medium text-fg-1 align-top">
                        {fieldMeta.verbose_name}
                      </td>
                      {objects.map((object) => (
                        <td key={object.id} className="px-4 py-2 text-sm text-fg-2 align-top">
                          <label className="flex items-start gap-2 cursor-pointer">
                            <input
                              type="radio"
                              name={field}
                              className="ck-checkbox mt-0.5"
                              style={{ borderRadius: '50%' }}
                              checked={selectedValues[field] === object.id}
                              onChange={() =>
                                setSelectedValues({ ...selectedValues, [field]: object.id })
                              }
                            />
                            <div className="flex-1 min-w-0">
                              <ReadOnlyField
                                value={object[field]}
                                metadata={metadata.fields[field]}
                              />
                            </div>
                          </label>
                        </td>
                      ))}
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="ck-btn ck-btn-secondary ck-btn-sm"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleMerge}
          disabled={mergeMutation.isPending}
          className="ck-btn ck-btn-primary ck-btn-sm"
        >
          {mergeMutation.isPending ? 'Merging…' : 'Merge records'}
        </button>
      </div>
    </div>
  );
}
