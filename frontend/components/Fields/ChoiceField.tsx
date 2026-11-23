import * as React from "react";
import Select from "react-select";
import BaseField, { BaseFieldProps } from "./BaseField";
import { selectStyles } from "./selectStyles";

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
          styles={selectStyles({ hasError })}
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
