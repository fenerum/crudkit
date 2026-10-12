import BaseField, { BaseFieldProps } from "./BaseField";

type CheckboxProps = BaseFieldProps;

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
        <input
          type="checkbox"
          name={fieldName}
          checked={value ?? false}
          onChange={(e) => onChange(e.target.checked)}
          onBlur={onBlur}
          ref={ref}
          className={`ck-checkbox ${hasError ? 'is-error' : ''}`}
        />
      )}
    </BaseField>
  );
}
