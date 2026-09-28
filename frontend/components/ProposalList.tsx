import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import moment from 'moment-timezone';
import CrudKitAPIClient from '../data/api';
import { invalidateObject } from '../data/invalidate';
import { url } from '../utils/urls';
import ProposalPayload, { PROPOSAL_ICON } from '../shared/ProposalPayload';
import { Badge, Icon } from './ui';
import { sourceLabel } from './History';

export type Proposal = {
  id: string;
  kind: string;
  label: string;
  reasoning?: string;
  payload: any;
  target?: string | null;
  source?: string;
  client?: string;
  created_at?: string;
};

function errorText(error: any): string {
  return error?.errors?.[0] || error?.message || 'Something went wrong.';
}

function ProposalRow({ proposal }: { proposal: Proposal }) {
  const client = useMemo(() => new CrudKitAPIClient(), []);
  const qc = useQueryClient();
  const decide = useMutation({
    mutationFn: (action: 'confirm' | 'skip') => client.action('ASP', proposal.id, action),
    onSuccess: (response: any) => {
      invalidateObject(qc, proposal.target || response?.outcome?.id);
      qc.invalidateQueries({ queryKey: ['list', 'ASP'] });
    },
  });
  const newType = proposal.kind === 'create' ? proposal.payload?.type : null;

  return (
    <div className="ck-inbox-row cursor-default" data-testid="proposal">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-bg-3 border border-border-1 inline-flex items-center justify-center text-fg-2">
        <Icon name={PROPOSAL_ICON[proposal.kind] || 'help-circle'} size={14} color="currentColor" />
      </div>
      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-fg-1 font-semibold truncate">{proposal.label}</span>
          <Badge>{sourceLabel(proposal, null)}</Badge>
          <span className="ml-auto text-2xs text-fg-3 font-mono flex-shrink-0">
            {proposal.created_at ? moment(proposal.created_at).fromNow(true) : ''}
          </span>
        </div>
        {proposal.target ? (
          <Link to={url(proposal.target)} className="block text-xs text-fg-3 hover:text-fg-1 font-mono truncate">
            {proposal.target}
          </Link>
        ) : (
          newType && (
            <Link to={url(newType)} className="block text-xs text-fg-3 hover:text-fg-1 truncate">
              New <span className="font-mono">{newType}</span>
            </Link>
          )
        )}
        <ProposalPayload kind={proposal.kind} payload={proposal.payload} />
        {proposal.reasoning && <div className="text-xs text-fg-3 italic">{proposal.reasoning}</div>}
        {decide.isError && <div className="text-xs text-danger">{errorText(decide.error)}</div>}
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            className="ck-btn ck-btn-primary ck-btn-sm"
            disabled={decide.isPending}
            onClick={() => decide.mutate('confirm')}
          >
            {decide.isPending && decide.variables === 'confirm' ? 'Applying…' : 'Confirm'}
          </button>
          <button
            type="button"
            className="ck-btn ck-btn-secondary ck-btn-sm"
            disabled={decide.isPending}
            onClick={() => decide.mutate('skip')}
          >
            Skip
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProposalList({ proposals }: { proposals: Proposal[] }) {
  return (
    <div className="rounded-lg border border-border-1 bg-bg-1 overflow-hidden">
      {proposals.map((proposal) => (
        <ProposalRow key={proposal.id} proposal={proposal} />
      ))}
    </div>
  );
}
