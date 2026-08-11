import * as React from "react";
import moment from "moment-timezone";
import BaseField, { BaseFieldProps } from "./BaseField";

interface GenericInputFieldProps extends BaseFieldProps {
  metadata: BaseFieldProps["metadata"] & {
    type: string;
  };
}

// Fallback for any field types that don't have a dedicated component
export default function GenericInputField({
  fieldName,
  defaultValue,
  metadata,
  ...rest
}: GenericInputFieldProps) {
  let formattedDefaultValue: any = defaultValue;
  if (metadata.type === "DateField" && defaultValue) {
    formattedDefaultValue = moment(defaultValue).format("YYYY-MM-DD");
  } else if (metadata.type === "DateTimeField" && defaultValue) {
    formattedDefaultValue = moment(defaultValue).format("YYYY-MM-DDTHH:mm");
  } else if (defaultValue !== undefined && defaultValue !== null) {
    formattedDefaultValue = String(defaultValue);
  } else {
    formattedDefaultValue = "";
  }

  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={formattedDefaultValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => {
        const inputType = ({
          "CharField": "text",
          "DecimalField": "number",
          "DateField": "date",
          "DateTimeField": "datetime-local",
          "BooleanField": "checkbox",
          "ImageField": "file",
        } as Record<string, string>)[metadata.type] || "text";

        return (
          <div>
            <input
              type={inputType}
              name={fieldName}
              value={value ?? ""}
              checked={inputType === "checkbox" ? Boolean(value) : undefined}
              onChange={(e) => {
                if (inputType === "checkbox") {
                  onChange(e.target.checked);
                } else if (inputType === "file") {
                  onChange(e.target.value);
                } else {
                  onChange(e.target.value);
                }
              }}
              onBlur={onBlur}
              ref={ref}
              required={metadata.required}
              className={`block w-full rounded-md border-0 py-1.5 text-fg-1 bg-bg-2 ring-1 ring-inset ${
                hasError ? 'ring-danger' : 'ring-border-1'
              } placeholder:text-fg-3 focus:ring-2 focus:ring-inset focus:ring-primary-400 sm:text-sm sm:leading-6`}
            />
            <span className="text-xs text-fg-3 mt-1">Field type: {metadata.type}</span>
          </div>
        );
      }}
    </BaseField>
  );
}
