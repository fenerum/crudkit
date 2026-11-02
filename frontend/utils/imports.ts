// What a spreadsheet import did or would do, as the import endpoint reports it.
export type ImportCounts = {
  created: number;
  updated: number;
  unchanged: number;
  skipped: number;
  error: number;
};

// "2 new, 1 to update and 1 skipped": the non-zero counts of a preview.
export function describeCounts(counts: ImportCounts): string {
  const parts = [
    counts.created && `${counts.created} new`,
    counts.updated && `${counts.updated} to update`,
    counts.unchanged && `${counts.unchanged} unchanged`,
    counts.skipped && `${counts.skipped} skipped`,
    counts.error && `${counts.error} with errors`,
  ].filter(Boolean) as string[];
  if (!parts.length) return 'Nothing to import';
  return parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
}

// "Create 2 and update 1 customers?": what the person confirms before importing.
export function confirmImport(counts: ImportCounts, singular: string, plural: string): string {
  const actions = [counts.created && `create ${counts.created}`, counts.updated && `update ${counts.updated}`].filter(
    Boolean,
  ) as string[];
  const sentence = actions.join(' and ');
  const noun = counts.created + counts.updated === 1 ? singular : plural;
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)} ${noun}?`;
}
