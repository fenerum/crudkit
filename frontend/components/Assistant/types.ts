export type TranscriptItem =
  | { role: 'user' | 'assistant' | 'system'; text: string }
  | {
      role: 'proposal';
      id: number | string;
      kind: string;
      label: string;
      payload: any;
      reasoning?: string;
      target?: string | null;
      target_label?: string | null;
      status: string;
      summary?: string;
    };

export type IncomingEvent =
  | { type: 'ready'; session: string }
  | { type: 'conversation'; id: string; title: string; transcript: TranscriptItem[] }
  | { type: 'assistant_message'; text: string }
  | {
      type: 'tool_call_pending';
      id: number | string;
      kind: string;
      label: string;
      payload: any;
      reasoning?: string;
      target?: string | null;
      target_label?: string | null;
    }
  | { type: 'tool_outcome'; id: number | string; ok: boolean; status: string; summary?: string; outcome?: any }
  | { type: 'error'; message: string };

export type Screen = Record<string, unknown>;

export type OutgoingEvent =
  | { type: 'auth'; token: string }
  | { type: 'open_conversation'; id: string | null }
  | { type: 'screen'; screen: Screen }
  | { type: 'user_message'; text: string }
  | { type: 'confirm'; id: number | string; ok: boolean };

export type Resolution = 'confirmed' | 'skipped' | 'failed';

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
      target?: string | null;
      targetLabel?: string | null;
      resolved?: Resolution;
      summary?: string;
    }
  | { kind: 'system'; id: string; text: string };
