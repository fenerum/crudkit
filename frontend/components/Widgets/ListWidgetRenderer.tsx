import { Link } from 'react-router-dom';
import { url } from '@/utils/urls';
import ReadOnlyField from '@/components/ReadOnlyField';

export interface ListWidgetRendererProps {
  title: string;
  objects: any[];
  metadata: any;
  displayFields: string[];
  data: {
    object: string;
    filters: Array<Array<any>>;
    limit?: number;
    display_fields?: string[];
  };
  loading: boolean;
  error: string | null;
  containerClassName?: string;
}

const ListWidgetRenderer = ({
  title,
  objects,
  metadata,
  displayFields,
  data,
  loading,
  error,
  containerClassName
}: ListWidgetRendererProps) => {
  // Loading state
  if (loading) {
    return (
      <div className="h-[350px] w-full rounded-lg bg-bg-1 border border-border-1 flex flex-col">
        <div className="p-3 border-b border-border-1 bg-bg-2">
          <h3 className="text-sm font-semibold text-fg-1">{title || 'List'}</h3>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center">
            <svg className="animate-spin h-6 w-6 text-primary-300" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="mt-2 text-xs text-fg-3">Loading…</span>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="h-[350px] w-full rounded-lg bg-bg-1 border border-border-1 flex flex-col">
        <div className="p-3 border-b border-border-1 bg-bg-2">
          <h3 className="text-sm font-semibold text-fg-1">{title || 'List'}</h3>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-danger text-sm">{error}</p>
        </div>
      </div>
    );
  }

  // Empty state
  if (!objects || objects.length === 0) {
    return (
      <div className="h-[350px] w-full rounded-lg bg-bg-1 border border-border-1 flex flex-col">
        <div className="p-3 border-b border-border-1 bg-bg-2">
          <h3 className="text-sm font-semibold text-fg-1">{title || 'List'}</h3>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-fg-3 text-sm">No items found</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`h-[350px] w-full rounded-lg bg-bg-1 border border-border-1 flex flex-col ${containerClassName || ''}`}>
      <div className="p-3 border-b border-border-1 bg-bg-2">
        <h3 className="text-sm font-semibold text-fg-1">{title || 'List'}</h3>
      </div>
      
      <div className="flex-1 overflow-x-hidden overflow-y-auto">
        <table className="w-full table-fixed" style={{ borderCollapse: 'collapse' }}>
          <thead className="bg-bg-2">
            <tr>
              <th scope="col" className="w-16 px-3 py-2 text-left eyebrow">
                ID
              </th>
              {displayFields.map(field => (
                <th
                  key={field}
                  scope="col"
                  className="px-3 py-2 text-left eyebrow truncate"
                >
                  {metadata?.fields[field]?.verbose_name || field}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.isArray(objects) ? objects.map(object => (
              <tr key={object.id} className="border-t border-border-1 hover:bg-bg-2">
                <td className="w-16 px-3 py-2">
                  <Link 
                    to={url(object.id)}
                    className="text-xs font-mono text-fg-3 hover:text-primary-300"
                  >
                    {object.id}
                  </Link>
                </td>
                {displayFields.map(field => (
                  <td key={field} className="px-3 py-2 text-sm text-fg-2 truncate max-w-[200px]">
                    <div className="truncate">
                      {metadata?.fields[field] ? (
                        <ReadOnlyField
                          value={object[field]}
                          metadata={metadata.fields[field]}
                          link={false}
                        />
                      ) : (
                        object[field] || '-'
                      )}
                    </div>
                  </td>
                ))}
              </tr>
            )) : (
              <tr>
                <td colSpan={displayFields.length + 1} className="px-3 py-4 text-center text-sm text-fg-3">
                  No data available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="p-3 border-t border-border-1 bg-bg-2 flex justify-center">
        <Link 
          to={`/${data.object}`}
          className="text-xs font-medium text-primary-300 hover:text-primary-200"
        >
          View all
        </Link>
      </div>
    </div>
  );
};

export default ListWidgetRenderer;