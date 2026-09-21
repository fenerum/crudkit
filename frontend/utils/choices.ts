// Display label for a stored choice value, falling back to the raw value.
export function choiceLabel(fieldMetadata: { choices?: [unknown, string][] } | undefined, value: unknown) {
  const match = fieldMetadata?.choices?.find(([choice]) => choice === value);
  return match ? match[1] : value;
}
