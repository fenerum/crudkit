import { Link } from 'react-router-dom';
import { Icon } from '../ui';
import { url } from '../../utils/urls';
import ProposalPayload, { PROPOSAL_ICON } from '../../shared/ProposalPayload';

type Props = {
  label: string;
  kind: string;
  payload: any;
  reasoning?: string;
  target?: string | null;
  targetLabel?: string | null;
  resolved?: 'confirmed' | 'skipped' | 'failed';
  summary?: string;
  // Set while a Confirm/Skip is on its way to the server.
  deciding?: 'confirm' | 'skip';
  onConfirm: () => void;
  onSkip: () => void;
  // Offered on confirmed proposals whose changes can be reverted.
  onUndo?: () => void;
  undone?: boolean;
};

export default function ConfirmCard({
  label,
  kind,
  payload,
  reasoning,
  target,
  targetLabel,
  resolved,
  summary,
  deciding,
  onConfirm,
  onSkip,
  onUndo,
  undone,
}: Props) {
  return (
    <div className="bg-bg-2 border border-bg-4 rounded-md p-3 text-sm space-y-2">
      <div className="flex items-center gap-2 text-fg-1 font-medium">
        <Icon name={PROPOSAL_ICON[kind] || 'help-circle'} size={14} color="currentColor" />
        <span>{label}</span>
      </div>
      {target && (
        <Link to={url(target)} className="block text-xs text-fg-3 hover:text-fg-1 truncate">
          <span className="font-mono">{target}</span>
          {targetLabel && ` · ${targetLabel}`}
        </Link>
      )}
      <ProposalPayload kind={kind} payload={payload} />
      {reasoning && <div className="text-xs text-fg-3 italic">{reasoning}</div>}
      {resolved ? (
        <div className="flex items-center gap-2">
          <div
            className={`flex-1 text-xs ${
              resolved === 'confirmed' ? 'text-success' : resolved === 'failed' ? 'text-danger' : 'text-fg-3'
            }`}
          >
            {resolved === 'confirmed' && (summary || 'Done.')}
            {resolved === 'skipped' && 'Skipped.'}
            {resolved === 'failed' && (summary || 'Failed.')}
          </div>
          {resolved === 'confirmed' &&
            (undone ? (
              <span className="text-xs text-fg-3">Undone.</span>
            ) : (
              onUndo && (
                <button type="button" className="ck-btn ck-btn-ghost ck-btn-sm" onClick={onUndo}>
                  Undo
                </button>
              )
            ))}
        </div>
      ) : deciding ? (
        <div className="flex items-center gap-1.5 text-xs text-fg-3">
          <span className="w-3 h-3 rounded-full border-2 border-fg-3 border-t-transparent animate-spin" />
          {deciding === 'confirm' ? 'Applying…' : 'Skipping…'}
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
