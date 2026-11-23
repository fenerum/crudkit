import BaseField, { BaseFieldProps } from "./BaseField";
import { inputClass } from "./inputClass";

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
          className={inputClass(hasError)}
        />
      )}
    </BaseField>
  );
}
