import BaseField, { BaseFieldProps } from "./BaseField";

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
          className={`block w-full rounded-md border-0 py-1.5 text-fg-1 bg-bg-2 ring-1 ring-inset ${
            hasError ? 'ring-danger' : 'ring-border-1'
          } placeholder:text-fg-3 focus:ring-2 focus:ring-inset focus:ring-primary-400 sm:text-sm sm:leading-6`}
        />
      )}
    </BaseField>
  );
}
