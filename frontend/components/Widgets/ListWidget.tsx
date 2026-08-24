import React, { useEffect, useState } from 'react';
import { fetchMetadata, fetchObjects } from '@/data/api';
import ListWidgetRenderer from './ListWidgetRenderer';

export interface ListWidgetProps {
  title: string;
  data: {
    object: string;
    filters: Array<Array<any>>;
    limit?: number;
    display_fields?: string[];
  };
  width?: number;
  containerClassName?: string;
}

const ListWidget = ({ title, data, width, containerClassName }: ListWidgetProps) => {
  const [objects, setObjects] = useState<any[]>([]);
  const [metadata, setMetadata] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  // Fields to display in the list - use backend-provided fields or defaults
  const defaultFields = ['name', 'status', 'due_at', 'priority', 'assigned_to_user'];
  const [displayFields, setDisplayFields] = useState<string[]>(
    data?.display_fields || defaultFields
  );

  useEffect(() => {
    const fetchData = async () => {
      if (!data || !data.object) {
        setError('No object type specified');
        setLoading(false);
        return;
      }

      try {
        // Fetch metadata for the object type
        const meta = await fetchMetadata(data.object);
        setMetadata(meta);

        // Use backend-provided fields or determine which fields to display based on available fields
        if (data.display_fields) {
          // Filter to ensure all fields exist in the metadata
          const availableFields = Object.keys(meta.fields);
          const fieldsToDisplay = data.display_fields.filter(field => availableFields.includes(field));
          setDisplayFields(fieldsToDisplay);
        } else {
          // Use default fields and filter based on available fields
          const availableFields = Object.keys(meta.fields);
          const fieldsToDisplay = defaultFields.filter(field => availableFields.includes(field));
          setDisplayFields(fieldsToDisplay);
        }

        // Prepare filters
        const filters: Record<string, any> = {};
        if (data.filters && Array.isArray(data.filters)) {
          data.filters.forEach(filter => {
            if (filter.length >= 3) {
              const [field, operator, value] = filter;
              if (operator === "=") {
                filters[`${field}`] = value;
              } else {
                filters[`${field}${operator ? `__${operator}` : ''}`] = value;
              }
            }
          });
        }

        // Add limit if specified
        if (data.limit) {
          filters['_limit'] = data.limit;
        } else {
          filters['_limit'] = 5; // Default limit
        }

        // Fetch objects with filters
        const result = await fetchObjects(data.object, filters);
        
        // Check if the result is paginated or a simple array
        if (result && result.isPaginated) {
          setObjects(result.results || []);
        } else {
          setObjects(Array.isArray(result) ? result : []);
        }
        
        setLoading(false);
      } catch (err) {
        console.error('Error fetching list data:', err);
        setError('Failed to load data');
        setLoading(false);
      }
    };

    fetchData();
  }, [data]);

  return (
    <ListWidgetRenderer
      title={title}
      objects={objects}
      metadata={metadata}
      displayFields={displayFields}
      data={data}
      loading={loading}
      error={error}
      containerClassName={containerClassName}
    />
  );
};

export default ListWidget;