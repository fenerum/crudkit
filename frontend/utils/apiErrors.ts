const UNPREFIXED_KEYS = new Set(['non_field_errors', '__all__', 'detail']);

function firstMessage(value: unknown): string {
  if (Array.isArray(value)) return firstMessage(value[0]);
  if (value && typeof value === 'object') return formatErrorDict(value as Record<string, unknown>);
  return String(value ?? '');
}

function formatErrorDict(errors: Record<string, unknown>, fields?: Record<string, { verbose_name?: string }>): string {
  return Object.entries(errors)
    .map(([key, value]) => {
      const message = firstMessage(value);
      if (UNPREFIXED_KEYS.has(key)) return message;
      const label = fields?.[key]?.verbose_name || key;
      return `${label}: ${message}`;
    })
    .filter(Boolean)
    .join('\n');
}

// Turns an error thrown by CrudKitAPIClient into a message fit for a toast,
// using the server's validation messages when there are any.
export function formatApiError(error: any, fields?: Record<string, { verbose_name?: string }>): string | null {
  if (!error) return null;
  const { errors } = error;
  if (Array.isArray(errors) && errors.length) return errors.map(String).join('\n');
  if (errors && typeof errors === 'object') {
    const message = formatErrorDict(errors, fields);
    if (message) return message;
  }
  if (error.errorData?.detail) return String(error.errorData.detail);
  return error.message || null;
}
