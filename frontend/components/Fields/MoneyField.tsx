import BaseField, { BaseFieldProps } from "./BaseField";

interface MoneyFieldValue {
  currency: string;
  amount: string;
  amount_default_currency: string;
  default_currency: string;
}

interface MoneyFieldProps extends BaseFieldProps {
  metadata: BaseFieldProps["metadata"] & {
    max_digits?: number;
    decimal_places?: number;
  };
}

export default function MoneyField({
  fieldName,
  defaultValue = "",
  metadata,
  ...rest
}: MoneyFieldProps) {
  let initialValue: MoneyFieldValue | string = "";

  if (typeof defaultValue === 'object' && defaultValue !== null && 'amount' in defaultValue) {
    initialValue = defaultValue as MoneyFieldValue;
  } else if (defaultValue !== undefined && defaultValue !== "") {
    const amount = typeof defaultValue === 'number'
      ? defaultValue.toFixed(2)
      : String(defaultValue);

    initialValue = {
      currency: "DKK",
      amount: amount,
      amount_default_currency: amount,
      default_currency: "DKK"
    };
  }

  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={initialValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange, onBlur, hasError, ref }) => {
        const handleChange = (text: string) => {
          const numericRegex = /^-?\d*\.?\d*$/;
          if (text === "" || numericRegex.test(text)) {
            const currentValue = value || {
              currency: "DKK",
              amount: "",
              amount_default_currency: "",
              default_currency: "DKK"
            };
            onChange({ ...currentValue, amount: text });
          }
        };

        const displayAmount = value && typeof value === 'object' && 'amount' in value
          ? value.amount
          : "";

        const currentCurrency = value && typeof value === 'object' && 'currency' in value
          ? value.currency
          : "DKK";

        return (
          <div className="flex flex-row items-center gap-2">
            <input
              type="number"
              name={fieldName}
              value={displayAmount}
              onChange={(e) => handleChange(e.target.value)}
              onBlur={onBlur}
              ref={ref}
              required={metadata.required}
              step={metadata.decimal_places ? `0.${"0".repeat(metadata.decimal_places-1)}1` : "any"}
              className={`ck-input ${hasError ? 'is-error' : ''} font-mono`}
              style={{ width: '100%', textAlign: 'right' }}
            />
            <span className="text-fg-3 text-xs font-mono">{currentCurrency}</span>
          </div>
        );
      }}
    </BaseField>
  );
}
