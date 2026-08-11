export type IncomingEvent =
  | { type: 'ready'; session: string }
  | { type: 'assistant_message'; text: string }
  | { type: 'tool_call_pending'; id: number | string; kind: string; label: string; payload: any; reasoning?: string }
  | { type: 'tool_outcome'; id: number | string; ok: boolean; status: string; summary?: string; outcome?: any }
  | { type: 'error'; message: string };

export type OutgoingEvent =
  | { type: 'auth'; token: string }
  | { type: 'user_message'; text: string }
  | { type: 'confirm'; id: number | string; ok: boolean };

export type ChatItem =
  | { kind: 'user'; id: string; text: string }
  | { kind: 'assistant'; id: string; text: string }
  | {
      kind: 'proposal';
      id: number | string;
      label: string;
      proposalKind: string;
      payload: any;
      reasoning?: string;
      resolved?: 'confirmed' | 'skipped' | 'failed';
      summary?: string;
    }
  | { kind: 'system'; id: string; text: string };
