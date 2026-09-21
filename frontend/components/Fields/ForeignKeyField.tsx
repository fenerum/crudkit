import * as React from "react";
import AsyncCreatableSelect from "react-select/async-creatable";
import BaseField, { BaseFieldProps } from "./BaseField";
import CrudKitAPIClient from "../../data/api";
import InlineCreateModal from "../InlineCreateModal";
import { useMetadata } from "../../utils/formHooks";

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
  }, [relatedModelType, client, fieldName]);

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
          name={fieldName}
          value={toOption(value)}
          styles={{
            control: (base: any, state: any) => ({
              ...base,
              minHeight: '34px',
              backgroundColor: 'var(--bg-2)',
              borderColor: hasError
                ? 'var(--danger)'
                : state.isFocused
                  ? 'var(--primary-400)'
                  : 'var(--border-1)',
              boxShadow: state.isFocused ? 'var(--shadow-focus)' : 'none',
              '&:hover': {
                borderColor: state.isFocused ? 'var(--primary-400)' : 'var(--border-2)',
              },
              borderRadius: 'var(--r-sm)',
              position: 'relative',
              zIndex: 1
            }),
            singleValue: (base: any) => ({ ...base, color: 'var(--fg-1)' }),
            input: (base: any) => ({ ...base, color: 'var(--fg-1)' }),
            placeholder: (base: any) => ({ ...base, color: 'var(--fg-3)' }),
            menu: (base: any) => ({
              ...base,
              backgroundColor: 'var(--bg-4)',
              border: '1px solid var(--border-2)',
              boxShadow: 'var(--shadow-menu)',
              zIndex: 9999
            }),
            option: (base: any, state: any) => ({
              ...base,
              backgroundColor: state.isSelected
                ? 'var(--bg-5)'
                : state.isFocused
                  ? 'var(--bg-3)'
                  : 'transparent',
              color: 'var(--fg-1)',
              cursor: 'pointer',
            }),
            indicatorSeparator: (base: any) => ({ ...base, backgroundColor: 'var(--border-1)' }),
            menuPortal: (base: any) => ({ ...base, zIndex: 9999 })
          }}
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
