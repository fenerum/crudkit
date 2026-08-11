import * as React from "react";
import BaseField, { BaseFieldProps } from "./BaseField";

interface DecimalFieldProps extends BaseFieldProps {
  metadata: BaseFieldProps["metadata"] & {
    max_digits?: number;
    decimal_places?: number;
  };
}

export default function DecimalField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: DecimalFieldProps) {
  const initialValue = defaultValue !== undefined ? String(defaultValue) : "";

  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={initialValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => (
        <input
          type="number"
          name={fieldName}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          ref={ref}
          required={metadata.required}
          step={metadata.decimal_places ? `0.${"0".repeat(metadata.decimal_places-1)}1` : "any"}
          className={`block w-full rounded-md border-0 py-1.5 text-fg-1 bg-bg-2 ring-1 ring-inset ${
            hasError ? 'ring-danger' : 'ring-border-1'
          } placeholder:text-fg-3 focus:ring-2 focus:ring-inset focus:ring-primary-400 sm:text-sm sm:leading-6`}
        />
      )}
    </BaseField>
  );
}
