import { useQuery } from '@tanstack/react-query';
import InlineList from './InlineList';
import Feed from './Feed';
import CrudKitAPIClient from '@/data/api';
import ActionButton from './ActionButton';
import { url } from '@/utils/urls';

/**
 * Component for managing and rendering inline relationship lists.
 *
 * @param {string} type - The model type code (e.g., "CMP" for company)
 * @param {string} id - The object ID to fetch inlines for
 * @param {object} metadata - The parent object's metadata containing relations info
 * @param {object} layout - The layout object containing inline field configurations
 */
export default function Inlines({ type, id, metadata, layout }) {
  const client = new CrudKitAPIClient();

  const hasInlines = !!(layout && layout.inlines && layout.inlines.length > 0);

  const inlineQuery = useQuery({
    queryKey: ['inlines-metadata', type, id],
    enabled: hasInlines && metadata !== null,
    queryFn: () => {
      if (!hasInlines || !metadata) return [];

      let inlineRequests = layout.inlines.map(async ([mdl, fields]) => {
        const related_field_name = metadata.relations.find((r) => r.related_model_type === mdl)?.field_name;
        const createParams = related_field_name ? {
          [related_field_name]: id
        } : {};

        return [
          mdl,
          fields,
          [],
          await client.metadata(mdl),
          createParams,
          id,
          related_field_name
        ];
      });

      return Promise.all(inlineRequests);
    }
  });

  if (!metadata || !layout) {
    return null;
  }

  if (hasInlines && inlineQuery.isPending) {
    return (
      <div className="mt-8">
        <p>Loading inline data...</p>
      </div>
    );
  }

  if (hasInlines && inlineQuery.isError) {
    return (
      <div className="mt-8">
        <p className="text-danger">Error loading inline data: {inlineQuery.error.message}</p>
      </div>
    );
  }

  const inlines = inlineQuery.data || [];

  if (inlines.length === 0) {
    return null;
  }

  return (
    <div className="mt-8">
      {inlines.map(([mdl, fields, _, inlineMetadata, createParams, parent_object_id, related_field_name]) => {
        if (mdl === "FEI") {
          return (
            <div key={mdl} className="mb-6">
              <Feed
                fields={fields}
                model={mdl}
                parent_object_id={parent_object_id}
                metadata={inlineMetadata}
                related_field_name={related_field_name}
                parentType={type}
              />
            </div>
          );
        }

        return (
          <div key={mdl} className="mb-6">
            <div className="flex flex-row justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-fg-1 capitalize">
                {inlineMetadata.verbose_name_plural}
              </h3>
              <ActionButton
                url={url(mdl, 'create') + (createParams ? new URLSearchParams(createParams).toString() : '')}
                text="New"
                color="indigo"
              />
            </div>

            <InlineList
              fields={fields}
              model={mdl}
              metadata={inlineMetadata}
              createParams={createParams}
              parent_object_id={parent_object_id}
              related_field_name={related_field_name}
            />
          </div>
        );
      })}
    </div>
  );
}
