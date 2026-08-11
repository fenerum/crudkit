import * as React from "react";
import AsyncSelect from "react-select/async";
import BaseField, { BaseFieldProps } from "./BaseField";
import CrudKitAPIClient from "../../data/api";

export interface ForeignKeyFieldProps extends BaseFieldProps {
  metadata: BaseFieldProps["metadata"] & {
    related_model_type?: string;
    blank?: boolean;
  };
}

export default function ForeignKeyField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: ForeignKeyFieldProps) {
  const client = React.useMemo(() => new CrudKitAPIClient(), []);
  const [debounceTimeout, setDebounceTimeout] = React.useState<ReturnType<typeof setTimeout> | null>(null);

  const defaultValueOption = React.useMemo(() => {
    if (defaultValue && typeof defaultValue === 'object' && defaultValue.id) {
      return {
        value: defaultValue.id,
        label: defaultValue.label || String(defaultValue.id)
      };
    }
    return null;
  }, [defaultValue]);

  const relatedModelType = metadata.related_model_type;

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
        <AsyncSelect
          name={fieldName}
          defaultValue={defaultValueOption}
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
          noOptionsMessage={() => "Type to search..."}
          isClearable={metadata.blank}
          placeholder={metadata.blank ? "Select..." : "Required - select an option"}
          loadingMessage={() => "Loading..."}
          classNames={{ control: () => "w-full" }}
          menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
          menuPosition="fixed"
        />
      )}
    </BaseField>
  );
}
