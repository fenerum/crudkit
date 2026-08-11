import * as React from "react";
import BaseField, { BaseFieldProps } from "./BaseField";

interface CharFieldProps extends BaseFieldProps {
  metadata: BaseFieldProps["metadata"] & {
    max_length?: number;
    min_length?: number;
  };
}

export default function CharField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: CharFieldProps) {
  const rules = {
    maxLength: metadata.max_length ? {
      value: metadata.max_length,
      message: `Maximum length is ${metadata.max_length} characters`
    } : undefined,
    minLength: metadata.min_length ? {
      value: metadata.min_length,
      message: `Minimum length is ${metadata.min_length} characters`
    } : undefined
  };

  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={defaultValue}
      metadata={metadata}
      rules={rules}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => (
        <input
          type="text"
          name={fieldName}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          ref={ref}
          required={metadata.required}
          maxLength={metadata.max_length}
          minLength={metadata.min_length}
          placeholder={metadata.help_text}
          className={`block w-full rounded-md border-0 py-1.5 text-fg-1 bg-bg-2 ring-1 ring-inset ${
            hasError ? 'ring-danger' : 'ring-border-1'
          } placeholder:text-fg-3 focus:ring-2 focus:ring-inset focus:ring-primary-400 sm:text-sm sm:leading-6`}
        />
      )}
    </BaseField>
  );
}
