import * as React from "react";
import { useController, useFormContext } from "react-hook-form";

// Base props that all field components should receive
export interface BaseFieldProps {
  fieldName: string;
  defaultValue?: any;
  label?: string;
  metadata: {
    required?: boolean;
    help_text?: string;
    [key: string]: any;
  };
  // Rules for validation (passed to react-hook-form)
  rules?: Record<string, any>;
}

interface BaseFieldWrapperProps extends BaseFieldProps {
  children: (props: {
    value: any;
    onChange: (value: any) => void;
    onBlur: () => void;
    error?: string;
    hasError: boolean;
    ref?: React.Ref<any>;
  }) => React.ReactNode;
}

/**
 * BaseField wrapper that handles form control using react-hook-form
 * All field components should use this as their base to ensure consistent behavior
 */
export default function BaseField({
  fieldName,
  defaultValue,
  label,
  metadata,
  rules = {},
  children
}: BaseFieldWrapperProps) {
  const formContext = useFormContext();

  const defaultRules = {
    required: metadata.required ? "This field is required" : false,
  };

  const fieldRules = { ...defaultRules, ...rules };

  const { control } = formContext;

  const { field, fieldState } = useController({
    name: fieldName,
    control,
    defaultValue,
    rules: fieldRules,
  });

  return (
    <div className="mb-4">
      {label && (
        <label className="block text-sm font-medium text-fg-1 mb-1">{label}</label>
      )}

      {children({
        value: field.value,
        onChange: field.onChange,
        onBlur: field.onBlur,
        error: fieldState.error?.message,
        hasError: !!fieldState.error,
        ref: field.ref,
      })}
    </div>
  );
}
