import BaseField, { BaseFieldProps } from "./BaseField";

type JSONFieldProps = BaseFieldProps;

export default function JSONField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: JSONFieldProps) {
  const formattedDefaultValue = defaultValue
    ? typeof defaultValue === 'string'
      ? defaultValue
      : JSON.stringify(defaultValue, null, 2)
    : "";

  const validateJSON = (value: unknown) => {
    if (value == null) return true;
    if (typeof value !== "string") return true;
    if (value.trim() === "") return true;
    try {
      JSON.parse(value);
      return true;
    } catch (error) {
      return (error as Error).message;
    }
  };

  const rules = { validate: { validJson: validateJSON } };

  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={formattedDefaultValue}
      metadata={metadata}
      rules={rules}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => {
        // Form state may carry an already-parsed array/object (from
        // /initial/ prefills or the detail endpoint). Render it as JSON so
        // the user sees `["id", "name"]` instead of `id,name` from
        // Array.prototype.toString().
        const displayValue =
          typeof value === 'string'
            ? value
            : value == null
              ? ''
              : JSON.stringify(value, null, 2);
        return (
          <textarea
            name={fieldName}
            value={displayValue}
            onChange={(e) => onChange(e.target.value)}
            onBlur={onBlur}
            ref={ref}
            rows={8}
            className={`ck-input font-mono ${hasError ? 'is-error' : ''}`}
            style={{ width: '100%', resize: 'vertical', minHeight: 160, lineHeight: 1.45 }}
            placeholder={metadata.help_text || "Enter valid JSON"}
          />
        );
      }}
    </BaseField>
  );
}
