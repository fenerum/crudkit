import { Icon } from '../ui';

type Props = {
  label: string;
  kind: string;
  payload: any;
  reasoning?: string;
  resolved?: 'confirmed' | 'skipped' | 'failed';
  summary?: string;
  onConfirm: () => void;
  onSkip: () => void;
};

function prettyPayload(kind: string, payload: any): string {
  if (!payload) return '';
  if (kind === 'action') return payload.action || '';
  if (kind === 'patch') {
    try {
      return Object.entries(payload.fields || {})
        .map(([k, v]) => `${k} = ${JSON.stringify(v)}`)
        .join('\n');
    } catch {
      return JSON.stringify(payload.fields || {});
    }
  }
  if (kind === 'note') return payload.body || '';
  return JSON.stringify(payload);
}

const KIND_ICON: Record<string, string> = {
  action: 'zap',
  patch: 'edit-3',
  note: 'message-square',
};

export default function ConfirmCard({
  label,
  kind,
  payload,
  reasoning,
  resolved,
  summary,
  onConfirm,
  onSkip,
}: Props) {
  const body = prettyPayload(kind, payload);
  return (
    <div className="bg-bg-2 border border-bg-4 rounded-md p-3 text-sm space-y-2">
      <div className="flex items-center gap-2 text-fg-1 font-medium">
        <Icon name={KIND_ICON[kind] || 'help-circle'} size={14} color="currentColor" />
        <span>{label}</span>
      </div>
      {body && (
        <pre className="text-xs text-fg-2 whitespace-pre-wrap break-words font-mono bg-bg-1 rounded px-2 py-1">
          {body}
        </pre>
      )}
      {reasoning && <div className="text-xs text-fg-3 italic">{reasoning}</div>}
      {resolved ? (
        <div
          className={`text-xs ${
            resolved === 'confirmed' ? 'text-success' : resolved === 'failed' ? 'text-danger' : 'text-fg-3'
          }`}
        >
          {resolved === 'confirmed' && (summary || 'Done.')}
          {resolved === 'skipped' && 'Skipped.'}
          {resolved === 'failed' && (summary || 'Failed.')}
        </div>
      ) : (
        <div className="flex gap-2 pt-1">
          <button type="button" className="ck-btn ck-btn-primary ck-btn-sm" onClick={onConfirm}>
            Confirm
          </button>
          <button type="button" className="ck-btn ck-btn-secondary ck-btn-sm" onClick={onSkip}>
            Skip
          </button>
        </div>
      )}
    </div>
  );
}
