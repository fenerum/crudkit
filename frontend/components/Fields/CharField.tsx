import BaseField, { BaseFieldProps } from "./BaseField";
import { inputClass } from "./inputClass";

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
          className={inputClass(hasError)}
        />
      )}
    </BaseField>
  );
}
