import BaseField, { BaseFieldProps } from "./BaseField";
import { inputClass } from "./inputClass";

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
          rows={5}
          className={inputClass(hasError)}
        />
      )}
    </BaseField>
  );
}
