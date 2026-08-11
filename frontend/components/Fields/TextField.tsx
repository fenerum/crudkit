import * as React from "react";
import BaseField, { BaseFieldProps } from "./BaseField";

interface TextFieldProps extends BaseFieldProps {
  metadata: BaseFieldProps["metadata"] & {
    max_length?: number;
  };
}

export default function TextField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: TextFieldProps) {
  const rules = {
    maxLength: metadata.max_length ? {
      value: metadata.max_length,
      message: `Maximum length is ${metadata.max_length} characters`
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
        <textarea
          name={fieldName}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          ref={ref}
          required={metadata.required}
          maxLength={metadata.max_length}
          placeholder={metadata.help_text}
          rows={5}
          className={`block w-full rounded-md border-0 py-1.5 text-fg-1 bg-bg-2 ring-1 ring-inset ${
            hasError ? 'ring-danger' : 'ring-border-1'
          } placeholder:text-fg-3 focus:ring-2 focus:ring-inset focus:ring-primary-400 sm:text-sm sm:leading-6`}
        />
      )}
    </BaseField>
  );
}
