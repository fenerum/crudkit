// What an AssistantProposal would do, as shown on its Confirm card in the
// assistant sidebar and in the Inbox.

// Tooltip on actions marked requires_approval: people run them directly.
export const APPROVAL_HINT = 'Connected apps and agents need your approval to run this';

export const PROPOSAL_ICON: Record<string, string> = {
  action: 'zap',
  patch: 'edit-3',
  create: 'plus',
  note: 'message-square',
  revert: 'rotate-ccw',
};

function fieldLines(fields: Record<string, unknown> | undefined): string[] {
  return Object.entries(fields || {}).map(([k, v]) => `${k} = ${JSON.stringify(v)}`);
}

export function prettyPayload(kind: string, payload: any): string {
  if (!payload) return '';
  if (kind === 'action') return payload.action || '';
  if (kind === 'patch') return fieldLines(payload.fields).join('\n');
  if (kind === 'create') return [`Create ${payload.type}`, ...fieldLines(payload.fields)].join('\n');
  if (kind === 'note') return payload.body || '';
  return JSON.stringify(payload);
}

export default function ProposalPayload({ kind, payload }: { kind: string; payload: any }) {
  const body = prettyPayload(kind, payload);
  if (!body) return null;
  return (
    <pre className="text-xs text-fg-2 whitespace-pre-wrap break-words font-mono bg-bg-1 rounded px-2 py-1">{body}</pre>
  );
}
