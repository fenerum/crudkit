import * as React from "react";
import Select from "react-select";
import BaseField, { BaseFieldProps } from "./BaseField";

export interface ChoiceFieldProps extends BaseFieldProps {
  metadata: BaseFieldProps["metadata"] & {
    choices?: [string | number, string][];
    blank?: boolean;
    default?: any;
  };
}

export default function ChoiceField({
  fieldName,
  defaultValue,
  metadata,
  ...rest
}: ChoiceFieldProps) {
  // Use default value from metadata if not provided in props
  // For required fields with no default, use the first choice option if available
  let initialValue = defaultValue ?? metadata.default ?? "";

  if (metadata.required && !defaultValue && !metadata.default &&
      metadata.choices && Array.isArray(metadata.choices) && metadata.choices.length > 0 && !initialValue) {
    initialValue = metadata.choices[0][0];
  }

  const selectOptions = React.useMemo(() => {
    if (!metadata.choices || !Array.isArray(metadata.choices)) return [];
    return metadata.choices.map(([value, label]) => ({ value, label }));
  }, [metadata.choices]);

  const defaultOption = React.useMemo(() => {
    if (!initialValue || !selectOptions.length) return null;
    return selectOptions.find(option => option.value === initialValue) || null;
  }, [initialValue, selectOptions]);

  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={initialValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError }) => (
        <Select
          name={fieldName}
          defaultValue={defaultOption}
          value={selectOptions.find(option => option.value === value) || null}
          options={selectOptions}
          onChange={(selectedOption: any) => {
            onChange(selectedOption ? selectedOption.value : "");
          }}
          onBlur={onBlur}
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
          isClearable={metadata.blank}
          placeholder={metadata.blank ? "Select..." : "Required - select an option"}
          noOptionsMessage={() => "No options available"}
          classNames={{ control: () => "w-full" }}
          menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
          menuPosition="fixed"
        />
      )}
    </BaseField>
  );
}
