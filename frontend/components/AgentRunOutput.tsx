// What a background agent run said and proposed (or, for a dry run, would
// have proposed), shown under the run's properties.
import { Link } from 'react-router-dom';
import { url } from '../utils/urls';
import ProposalPayload, { PROPOSAL_ICON } from '../shared/ProposalPayload';
import { Badge, Icon } from './ui';

// Rendered here instead of as plain fields.
export const AGENT_RUN_BLOCK_FIELDS = ['output', 'preview', 'error'];

type PreviewItem = {
  id?: string | null;
  kind: string;
  label: string;
  payload: any;
  reasoning?: string;
  target?: string | null;
  target_label?: string | null;
  dry_run?: boolean;
  status?: string;
  error?: string;
};

const STATUS_LABEL: Record<string, string> = {
  pending: 'Waiting for approval',
  confirmed: 'Applied',
  skipped: 'Skipped',
  failed: 'Failed',
};

function PreviewRow({ item }: { item: PreviewItem }) {
  const status = item.dry_run ? 'Dry run' : STATUS_LABEL[item.status || 'pending'];
  return (
    <div className="flex gap-3 px-3 py-2.5" data-testid="agent-run-proposal">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-bg-3 border border-border-1 inline-flex items-center justify-center text-fg-2">
        <Icon name={PROPOSAL_ICON[item.kind] || 'help-circle'} size={14} color="currentColor" />
      </div>
      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex items-center gap-2 text-sm">
          {item.id ? (
            <Link to={url(item.id)} className="text-fg-1 font-semibold truncate hover:underline">
              {item.label}
            </Link>
          ) : (
            <span className="text-fg-1 font-semibold truncate">{item.label}</span>
          )}
          <Badge>{status}</Badge>
        </div>
        {item.target && (
          <Link to={url(item.target)} className="block text-xs text-fg-3 hover:text-fg-1 truncate">
            {item.target_label || item.target} <span className="font-mono">{item.target}</span>
          </Link>
        )}
        <ProposalPayload kind={item.kind} payload={item.payload} />
        {item.reasoning && <div className="text-xs text-fg-3 italic">{item.reasoning}</div>}
        {item.error && <div className="text-xs text-danger">{item.error}</div>}
      </div>
    </div>
  );
}

export default function AgentRunOutput({ run }: { run: any }) {
  const preview: PreviewItem[] = Array.isArray(run?.preview) ? run.preview : [];
  const finished = run?.status === 'succeeded' || run?.status === 'failed';
  return (
    <section className="mt-6 space-y-4" data-testid="agent-run-output">
      {run?.error && (
        <div className="flex items-start gap-2.5 rounded-md border border-border-1 bg-bg-2 px-3.5 py-2.5 text-sm">
          <span className="text-danger flex-shrink-0 mt-0.5">
            <Icon name="alert-circle" size={14} color="currentColor" />
          </span>
          <span className="text-fg-1 whitespace-pre-wrap break-words">{run.error}</span>
        </div>
      )}
      {run?.output && (
        <div>
          <h3 className="text-sm font-semibold text-fg-1 tracking-tight mb-1.5">Summary</h3>
          <p className="text-sm text-fg-2 whitespace-pre-wrap break-words">{run.output}</p>
        </div>
      )}
      <div>
        <h3 className="text-sm font-semibold text-fg-1 tracking-tight mb-1.5">
          {run?.dry_run ? 'Would propose' : 'Proposals'}
        </h3>
        {preview.length > 0 ? (
          <div className="rounded-lg border border-border-1 bg-bg-1 divide-y divide-border-1 overflow-hidden">
            {preview.map((item, i) => (
              <PreviewRow key={item.id || i} item={item} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-fg-3">{finished ? 'Nothing proposed.' : 'The run has not finished yet.'}</p>
        )}
      </div>
    </section>
  );
}
