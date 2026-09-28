import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { toast } from 'react-toastify';
import CrudKitAPIClient from '../data/api';
import { invalidateRecords } from '../data/invalidate';
import { useAuth } from '../context/AuthContext';
import { formatApiError } from '../utils/apiErrors';
import { choiceLabel } from '../utils/choices';
import { url } from '../utils/urls';
import Modal from './Modal';
import { Badge, Button } from './ui';

const HIDDEN_FIELDS = ['deleted', 'merged_into'];
const CK_ID = /^[A-Z]{3}\d+$/;

const ACTION_TITLES = {
  create: 'Created',
  update: 'Updated',
  delete: 'Deleted',
  restore: 'Restored',
  action: 'Ran an action',
  merge: 'Merged',
  revert: 'Reverted a change',
};

export function sourceLabel(batch, currentUser) {
  const who = batch.by?.label || 'Someone';
  switch (batch.source) {
    case 'ui':
      return batch.by && batch.by.id === currentUser?.id ? 'You' : who;
    case 'api':
      return batch.client ? `API: ${batch.client}` : 'API';
    case 'mcp':
      return batch.client ? `MCP: ${batch.client}` : 'MCP';
    case 'assistant':
      return 'Assistant';
    case 'agent':
      return batch.client ? `Agent: ${batch.client}` : 'Agent';
    case 'revert':
      return 'Undo';
    case 'system':
      return 'System';
    default:
      return who;
  }
}

function Value({ field, value }) {
  if (value === null || value === undefined || value === '') return <span className="text-fg-4">—</span>;
  if (typeof value === 'string' && CK_ID.test(value)) {
    return (
      <Link to={url(value)} className="text-primary-300 hover:underline">
        {value}
      </Link>
    );
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return <span className="font-mono">{JSON.stringify(value)}</span>;
  return String(choiceLabel(field, value));
}

function Diff({ entries, fields }) {
  const rows = entries
    .filter((entry) => entry.action !== 'delete')
    .flatMap((entry) => Object.entries(entry.field_changes).map(([name, change]) => [entry.id, name, change]))
    .filter(([, name]) => !HIDDEN_FIELDS.includes(name));
  if (!rows.length) return null;
  return (
    <table className="w-full text-sm mt-2">
      <tbody>
        {rows.map(([entryId, name, [before, after]]) => (
          <tr key={`${entryId}-${name}`} className="border-t border-border-1">
            <td className="py-1.5 pr-3 text-fg-3 w-1/4 align-top">{fields?.[name]?.verbose_name || name}</td>
            <td className="py-1.5 pr-3 text-fg-3 line-through decoration-fg-4 align-top break-all">
              <Value field={fields?.[name]} value={before} />
            </td>
            <td className="py-1.5 text-fg-1 align-top break-all">
              <Value field={fields?.[name]} value={after} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ConflictDialog({ conflicts, fields, onCancel, onForce, isPending }) {
  return (
    <Modal onClose={onCancel} className="max-w-lg">
      <h2 className="text-lg font-semibold text-fg-1 mb-2">Changed since</h2>
      <p className="text-sm text-fg-2 mb-3">
        These values were changed again after this edit. Reverting anyway overwrites them.
      </p>
      <ul className="text-sm space-y-1 mb-4">
        {conflicts.map((conflict, i) => (
          <li key={i} className="text-fg-2">
            <span className="text-fg-1">{conflict.label || conflict.object}</span>
            {conflict.reason && ` · ${conflict.reason}`}
            {conflict.field && (
              <>
                {' · '}
                {fields?.[conflict.field]?.verbose_name || conflict.field}: now{' '}
                <Value field={fields?.[conflict.field]} value={conflict.current} />, expected{' '}
                <Value field={fields?.[conflict.field]} value={conflict.expected} />
              </>
            )}
          </li>
        ))}
      </ul>
      <div className="flex justify-end gap-2">
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="danger" onClick={onForce} disabled={isPending}>
          Revert anyway
        </Button>
      </div>
    </Modal>
  );
}

function Batch({ batch, fields, currentUser, onRevert, isReverting }) {
  const source = sourceLabel(batch, currentUser);
  const title = batch.label || ACTION_TITLES[batch.actions[0]] || 'Changed';
  return (
    <section className="rounded-md border border-border-1 bg-bg-1 px-3 py-2.5" data-testid="history-batch">
      <header className="flex items-center gap-2 text-sm">
        <Badge>{source}</Badge>
        <span className="font-medium text-fg-1">{title}</span>
        {batch.by && source !== 'You' && source !== batch.by.label && (
          <span className="text-fg-3">by {batch.by.label}</span>
        )}
        <span className="text-xs text-fg-3">
          {new Date(batch.at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
        </span>
        <span className="flex-1" />
        {batch.reverted ? (
          <span className="text-xs text-fg-3">Reverted</span>
        ) : (
          batch.revertible && (
            <Button size="sm" icon="rotate-ccw" onClick={onRevert} disabled={isReverting}>
              Revert
            </Button>
          )
        )}
      </header>
      <Diff entries={batch.entries} fields={fields} />
      {batch.other_records > 0 && (
        <div className="text-xs text-fg-3 mt-2">
          Also changed {batch.other_records} other record{batch.other_records === 1 ? '' : 's'}; reverting undoes
          those too.
        </div>
      )}
    </section>
  );
}

export default function History({ type, id, metadata }) {
  const client = new CrudKitAPIClient();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [conflicting, setConflicting] = useState(null);

  const historyQuery = useQuery({
    queryKey: ['history', type, id],
    queryFn: () => client.history(type, id),
  });

  const revertMutation = useMutation({
    mutationFn: ({ changeSet, force }) => client.revertChangeSet(changeSet, force),
    onSuccess: (result, { changeSet }) => {
      if (result.conflicts) {
        setConflicting({ changeSet, conflicts: result.conflicts });
        return;
      }
      setConflicting(null);
      invalidateRecords(queryClient);
      toast.success('Change reverted');
    },
    onError: (error) => toast.error(`Revert failed: ${formatApiError(error)}`),
  });

  if (historyQuery.isPending) return <div className="text-sm text-fg-3 animate-pulse">Loading…</div>;
  if (historyQuery.isError) return <div className="text-sm text-danger">Couldn&apos;t load the history.</div>;
  if (!historyQuery.data.length) return <div className="text-sm text-fg-3">No changes recorded yet.</div>;

  return (
    <div className="flex flex-col gap-3">
      {historyQuery.data.map((batch) => (
        <Batch
          key={batch.change_set || batch.entries[0].id}
          batch={batch}
          fields={metadata?.fields}
          currentUser={user}
          isReverting={revertMutation.isPending}
          onRevert={() => revertMutation.mutate({ changeSet: batch.change_set, force: false })}
        />
      ))}
      {conflicting && (
        <ConflictDialog
          conflicts={conflicting.conflicts}
          fields={metadata?.fields}
          isPending={revertMutation.isPending}
          onCancel={() => setConflicting(null)}
          onForce={() => revertMutation.mutate({ changeSet: conflicting.changeSet, force: true })}
        />
      )}
    </div>
  );
}
