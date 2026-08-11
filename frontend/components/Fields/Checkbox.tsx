import * as React from "react";
import BaseField, { BaseFieldProps } from "./BaseField";

interface CheckboxProps extends BaseFieldProps {}

export default function Checkbox({
  fieldName,
  defaultValue = false,
  metadata,
  ...rest
}: CheckboxProps) {
  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={defaultValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            name={fieldName}
            checked={value ?? false}
            onChange={(e) => onChange(e.target.checked)}
            onBlur={onBlur}
            ref={ref}
            className={`ck-checkbox ${hasError ? 'is-error' : ''}`}
          />
          <span className="text-sm text-fg-2">
            {metadata.help_text || ""}
          </span>
        </label>
      )}
    </BaseField>
  );
}
