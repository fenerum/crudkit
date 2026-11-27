import BaseField, { BaseFieldProps } from "./BaseField";
import { inputClass } from "./inputClass";

type DateFieldProps = BaseFieldProps;

export default function DateField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: DateFieldProps) {
  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={defaultValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => (
        <input
          type="date"
          name={fieldName}
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          ref={ref}
          required={metadata.required}
          className={inputClass(hasError)}
        />
      )}
    </BaseField>
  );
}
