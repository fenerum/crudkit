const NUMERIC_TYPE = /(Integer|Decimal|Float|Money)Field$/;

// CrudKitPositiveIntegerField holds CK-IDs and choice fields render labels, so
// neither is shown as a number.
export function isNumericField(meta: { type?: string; choices?: unknown } | undefined) {
  const type = meta?.type || "";
  return NUMERIC_TYPE.test(type) && type !== "CrudKitPositiveIntegerField" && !meta?.choices;
}

// Groups thousands in the browser's locale, keeping the decimals the value
// arrived with ("0.00" stays "0.00", "1234" gets none).
export function formatNumber(value: string | number) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  const decimals = String(value).split(".")[1]?.length ?? 0;
  return number.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
