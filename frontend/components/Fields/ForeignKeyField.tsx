import * as React from "react";
import AsyncCreatableSelect from "react-select/async-creatable";
import BaseField, { BaseFieldProps } from "./BaseField";
import CrudKitAPIClient from "../../data/api";
import InlineCreateModal from "../InlineCreateModal";
import { useMetadata } from "../../utils/formHooks";
import { selectStyles } from "./selectStyles";

export interface ForeignKeyFieldProps extends BaseFieldProps {
  metadata: BaseFieldProps["metadata"] & {
    related_model_type?: string;
    blank?: boolean;
  };
}

function toOption(value: any) {
  if (value && typeof value === 'object' && value.id) {
    return { value: value.id, label: value.label || String(value.id) };
  }
  return null;
}

export default function ForeignKeyField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: ForeignKeyFieldProps) {
  const client = React.useMemo(() => new CrudKitAPIClient(), []);
  const [debounceTimeout, setDebounceTimeout] = React.useState<ReturnType<typeof setTimeout> | null>(null);

  // Text typed when "Create new…" was chosen; non-null while the modal is open.
  const [creating, setCreating] = React.useState<string | null>(null);

  const relatedModelType = metadata.related_model_type;
  // Set by dependent fields (utils/dependentFields.ts): only offer linked records
  // that match this record, e.g. tickets of the deal's customer.
  const listFilter: Record<string, string> | undefined = metadata.list_filter;
  const filterKey = listFilter ? JSON.stringify(listFilter) : "";
  const { metadata: relatedMetadata } = useMetadata(relatedModelType);
  const canCreate = !!(relatedMetadata?.can_create && relatedMetadata?.inline_create);
  const relatedName = relatedMetadata?.verbose_name || relatedModelType;

  const loadOptions = React.useCallback(async (inputValue: string) => {
    if (!relatedModelType) {
      console.error('No related_model_type available for', fieldName);
      return [];
    }

    try {
      const response: any = await client.list(relatedModelType, {
        ...(listFilter || {}),
        _q: inputValue,
        _fields: "id,label,object_images"
      });

      if (response && response.isPaginated) {
        return (response.results || []).map((item: any) => ({
          value: item.id,
          label: item.label || String(item.id)
        }));
      } else if (Array.isArray(response)) {
        return response.map((item: any) => ({
          value: item.id,
          label: item.label || String(item.id)
        }));
      }

      return [];
    } catch (err) {
      console.error('Error fetching choices for', relatedModelType, err);
      return [];
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [relatedModelType, client, fieldName, filterKey]);

  const debouncedLoadOptions = React.useCallback((inputValue: string, callback: (options: any[]) => void) => {
    if (debounceTimeout) {
      clearTimeout(debounceTimeout);
    }

    const timeout = setTimeout(async () => {
      const options = await loadOptions(inputValue);
      callback(options);
    }, 300);

    setDebounceTimeout(timeout);
  }, [debounceTimeout, loadOptions]);

  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={defaultValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError }) => (
        <>
        <AsyncCreatableSelect
          // Remount when the filter changes, so the default options reload.
          key={filterKey}
          name={fieldName}
          value={toOption(value)}
          styles={selectStyles({ hasError })}
          onChange={(selectedOption: any) => {
            if (selectedOption) {
              onChange({ id: selectedOption.value, label: selectedOption.label });
            } else {
              onChange(null);
            }
          }}
          onBlur={onBlur}
          loadOptions={debouncedLoadOptions}
          defaultOptions={true}
          noOptionsMessage={() => "No matches"}
          isValidNewOption={() => canCreate}
          formatCreateLabel={(input: string) => input ? `+ Create ${relatedName} "${input}"` : `+ Create new ${relatedName}`}
          createOptionPosition="last"
          onCreateOption={(input: string) => setCreating(input)}
          isClearable={metadata.blank}
          placeholder={metadata.blank ? "Select..." : "Required - select an option"}
          loadingMessage={() => "Loading..."}
          classNames={{ control: () => "w-full" }}
          menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
          menuPosition="fixed"
        />
        {creating !== null && relatedModelType && (
          <InlineCreateModal
            type={relatedModelType}
            initialText={creating}
            onCreated={(data: { id: string; label?: string }) => {
              onChange({ id: data.id, label: data.label || String(data.id) });
              setCreating(null);
            }}
            onClose={() => setCreating(null)}
          />
        )}
        </>
      )}
    </BaseField>
  );
}
