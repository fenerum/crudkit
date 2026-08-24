import BaseField, { BaseFieldProps } from "./BaseField";

type DateTimeFieldProps = BaseFieldProps;

export default function DateTimeField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: DateTimeFieldProps) {
  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={defaultValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => {
        // Convert timezone-aware datetime to local timezone without the timezone part
        // HTML datetime-local input requires timezone-naive ISO format
        const dateLocalValue = (() => {
          if (!value) return "";

          try {
            const date = new Date(value);
            if (isNaN(date.getTime())) return "";
            return date.getFullYear() + '-' +
              String(date.getMonth() + 1).padStart(2, '0') + '-' +
              String(date.getDate()).padStart(2, '0') + 'T' +
              String(date.getHours()).padStart(2, '0') + ':' +
              String(date.getMinutes()).padStart(2, '0');
          } catch (e) {
            console.error("Error parsing date:", e);
            return "";
          }
        })();

        return (
          <input
            type="datetime-local"
            name={fieldName}
            value={dateLocalValue}
            onChange={(e) => onChange(e.target.value)}
            onBlur={onBlur}
            ref={ref}
            required={metadata.required}
            className={`block w-full rounded-md border-0 py-1.5 text-fg-1 bg-bg-2 ring-1 ring-inset ${
              hasError ? 'ring-danger' : 'ring-border-1'
            } placeholder:text-fg-3 focus:ring-2 focus:ring-inset focus:ring-primary-400 sm:text-sm sm:leading-6`}
          />
        );
      }}
    </BaseField>
  );
}
