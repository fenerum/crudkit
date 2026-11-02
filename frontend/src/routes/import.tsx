import { useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import CrudKitAPIClient, { ImportOptions } from '../../data/api';
import { useJobs } from '../../data/jobs';
import { useMetadata } from '../../utils/formHooks';
import { formatApiError } from '../../utils/apiErrors';
import { confirmImport, describeCounts, ImportCounts } from '../../utils/imports';
import { showSuccessToast } from '../../components/SuccessToast';
import ProgressBar from '../../components/ProgressBar';
import { Button, Icon } from '../../components/ui';

type ImportReport = {
  columns: string[];
  samples: Record<string, string[]>;
  fields: { name: string; label: string }[];
  mapping: Record<string, string>;
  match_fields: string[];
  counts: ImportCounts;
  rows: {
    row: number;
    status: string;
    id: string | null;
    errors: Record<string, string>;
  }[];
  _change_set?: string | null;
};

// How rows that match an existing record are handled.
const STRATEGIES = [
  { value: 'new', label: 'Create a new record for every row', mode: 'create', matches: false },
  { value: 'upsert', label: 'Update matching records, create the rest', mode: 'upsert', matches: true },
  { value: 'update', label: 'Only update matching records', mode: 'update', matches: true },
  { value: 'skip', label: 'Skip matching records, create the rest', mode: 'create', matches: true },
] as const;

const MAX_ERRORS_SHOWN = 100;

export default function Import() {
  const { segment: type } = useParams() as { segment: string };
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const client = new CrudKitAPIClient();
  const { metadata } = useMetadata(type);
  const jobs = useJobs();

  const [file, setFile] = useState<File | null>(null);
  // Null until the person changes it: the server's suggestion applies until then.
  const [mapping, setMapping] = useState<Record<string, string> | null>(null);
  const [strategyValue, setStrategyValue] = useState<(typeof STRATEGIES)[number]['value']>('new');
  // Null until the person picks one: the first match field a column goes into applies until then.
  const [matchOn, setMatchOn] = useState<string | null>(null);
  const strategy = STRATEGIES.find((s) => s.value === strategyValue)!;
  // The last preview that worked, so the controls stay while a changed choice is refused.
  const lastReport = useRef<ImportReport | undefined>(undefined);
  const known = lastReport.current;
  const mapped = Object.values(mapping ?? known?.mapping ?? {});
  const effectiveMatchOn = strategy.matches
    ? (matchOn ?? known?.match_fields.find((name) => mapped.includes(name)) ?? 'id')
    : null;

  const options = (dryRun: boolean): ImportOptions => ({
    mode: strategy.mode,
    match_on: effectiveMatchOn,
    mapping,
    dry_run: dryRun,
  });

  const preview = useQuery<ImportReport, any>({
    queryKey: ['import-preview', type, file?.name, file?.lastModified, mapping, strategyValue, effectiveMatchOn],
    queryFn: () => client.importRecords(type, file!, options(true)),
    enabled: !!file,
    retry: false,
  });
  if (preview.data) lastReport.current = preview.data;
  const report = lastReport.current;

  const commit = useMutation<ImportReport, any>({
    mutationFn: () => client.importRecords(type, file!, options(false)),
    onSuccess: (result) => {
      const imported = result.counts.created + result.counts.updated;
      queryClient.invalidateQueries({ queryKey: ['list', type] });
      showSuccessToast({
        label: `${imported} ${imported === 1 ? metadata?.verbose_name : metadata?.verbose_name_plural}`,
        verb: 'imported',
        onOpen: () => navigate(`/${type}`),
        changeSet: result._change_set,
        onUndone: () => queryClient.invalidateQueries({ queryKey: ['list', type] }),
      });
      navigate(`/${type}`);
    },
  });
  // A commit refused for bad rows answers with the report itself.
  const refused: ImportReport | undefined = commit.error?.errors?.rows ? commit.error.errors : undefined;
  const shown = refused || report;
  const running =
    commit.isPending && file ? jobs.find((j) => j.label === `Import ${file.name}` && j.status === 'running') : null;

  const chooseFile = (chosen: File | undefined) => {
    if (!chosen) return;
    setFile(chosen);
    setMapping(null);
    setMatchOn(null);
    lastReport.current = undefined;
    commit.reset();
  };

  const setColumn = (column: string, field: string) => {
    const next = { ...(mapping ?? report?.mapping ?? {}) };
    if (field) next[column] = field;
    else delete next[column];
    setMapping(next);
  };

  const submit = () => {
    if (shown && window.confirm(confirmImport(shown.counts, metadata?.verbose_name, metadata?.verbose_name_plural))) {
      commit.mutate();
    }
  };

  const requestError = commit.error && !refused ? commit.error : preview.error;
  const errorRows = shown?.rows.filter((row) => row.status === 'error') ?? [];
  const canImport =
    !!shown &&
    !preview.isFetching &&
    !preview.error &&
    !commit.isPending &&
    !shown.counts.error &&
    shown.counts.created + shown.counts.updated > 0;
  const currentMapping = mapping ?? report?.mapping ?? {};

  return (
    <div className="flex flex-col gap-4 max-w-4xl">
      <div>
        <h2 className="text-base font-semibold text-fg-1 tracking-tight">
          Import {metadata?.verbose_name_plural || type}
        </h2>
        <p className="text-xs text-fg-3 mt-1">
          Upload an Excel workbook (.xlsx) or a CSV file whose first row names the columns. Nothing is saved until you
          import, and an import can be undone.
        </p>
      </div>

      <label
        className="flex flex-col items-center justify-center gap-1.5 rounded-md border border-dashed border-border-2 bg-bg-1 px-4 py-6 text-sm text-fg-2 cursor-pointer hover:bg-bg-2"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          chooseFile(e.dataTransfer.files[0]);
        }}
      >
        <Icon name="upload" size={18} />
        {file ? (
          <span>
            <span className="font-medium text-fg-1">{file.name}</span> · choose another file
          </span>
        ) : (
          <span>Drop a file here, or choose one</span>
        )}
        <input
          type="file"
          accept=".xlsx,.csv"
          aria-label="Spreadsheet to import"
          className="sr-only"
          onChange={(e) => chooseFile(e.target.files?.[0])}
        />
      </label>

      {requestError && (
        <div
          className="rounded-md border bg-bg-2 px-3.5 py-2.5 text-sm"
          style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}
        >
          {formatApiError(requestError)}
        </div>
      )}

      {report && (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-fg-3">
              Existing records
              <select
                className="ck-input"
                value={strategyValue}
                onChange={(e) => setStrategyValue(e.target.value as typeof strategyValue)}
              >
                {STRATEGIES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            {strategy.matches && (
              <label className="flex flex-col gap-1 text-xs text-fg-3">
                Match on
                <select
                  className="ck-input"
                  value={effectiveMatchOn ?? ''}
                  onChange={(e) => setMatchOn(e.target.value)}
                >
                  {report.match_fields.map((name) => (
                    <option key={name} value={name}>
                      {report.fields.find((f) => f.name === name)?.label || name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <div className="overflow-hidden rounded-md border border-border-1 bg-bg-1">
            <table className="min-w-full" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr className="bg-bg-2 border-b border-border-1">
                  <th className="px-4 py-2 text-left eyebrow">Column</th>
                  <th className="px-4 py-2 text-left eyebrow">Sample</th>
                  <th className="px-4 py-2 text-left eyebrow">Import into</th>
                </tr>
              </thead>
              <tbody>
                {report.columns.map((column) => (
                  <tr key={column} className="border-b border-border-1 last:border-b-0">
                    <td className="px-4 py-2 text-sm font-medium text-fg-1">{column}</td>
                    <td className="px-4 py-2 text-sm text-fg-3 truncate max-w-xs">
                      {report.samples[column]?.join(', ')}
                    </td>
                    <td className="px-4 py-1.5">
                      <select
                        className="ck-input"
                        aria-label={`Field for ${column}`}
                        value={currentMapping[column] || ''}
                        onChange={(e) => setColumn(column, e.target.value)}
                      >
                        <option value="">Don&apos;t import</option>
                        {report.fields.map((field) => (
                          <option key={field.name} value={field.name}>
                            {field.label}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {shown && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-fg-1" aria-live="polite">
            {preview.isFetching ? 'Checking…' : describeCounts(shown.counts)}
          </p>
          {errorRows.length > 0 && (
            <div className="overflow-hidden rounded-md border border-border-1 bg-bg-1">
              <table className="min-w-full" style={{ borderCollapse: 'collapse' }} aria-label="Rows with errors">
                <thead>
                  <tr className="bg-bg-2 border-b border-border-1">
                    <th className="px-4 py-2 text-left eyebrow">Row</th>
                    <th className="px-4 py-2 text-left eyebrow">Column</th>
                    <th className="px-4 py-2 text-left eyebrow">Problem</th>
                  </tr>
                </thead>
                <tbody>
                  {errorRows.slice(0, MAX_ERRORS_SHOWN).flatMap((row) =>
                    Object.entries(row.errors).map(([column, message]) => (
                      <tr key={`${row.row}-${column}`} className="border-b border-border-1 last:border-b-0">
                        <td className="px-4 py-2 text-sm text-fg-2">{row.row}</td>
                        <td className="px-4 py-2 text-sm text-fg-2">{column}</td>
                        <td className="px-4 py-2 text-sm" style={{ color: 'var(--danger)' }}>
                          {message}
                        </td>
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {running && <ProgressBar done={running.done} total={running.total} label={running.label} />}

      <div className="flex justify-end gap-2">
        <Button size="sm" onClick={() => navigate(`/${type}`)}>
          Cancel
        </Button>
        <Button size="sm" variant="primary" icon="upload" onClick={submit} disabled={!canImport}>
          {commit.isPending ? 'Importing…' : 'Import'}
        </Button>
      </div>
    </div>
  );
}
