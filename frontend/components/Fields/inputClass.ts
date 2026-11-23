// Shared look of the plain text-like inputs (char, text, number, date, …).
export function inputClass(hasError: boolean): string {
  return (
    'block w-full rounded-md border-0 py-1 text-fg-1 bg-bg-1 ring-1 ring-inset ' +
    (hasError ? 'ring-danger' : 'ring-border-3 hover:ring-fg-4') +
    ' placeholder:text-fg-4 focus:ring-1 focus:ring-inset focus:ring-primary-400 focus:shadow-focus sm:text-md sm:leading-5'
  );
}
