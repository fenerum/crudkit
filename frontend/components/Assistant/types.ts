export type Step = { id: string; label: string; ok: boolean | null };

export type TranscriptItem =
  | { role: 'user' | 'assistant' | 'system'; text: string }
  | { role: 'activity'; steps: Step[]; seconds: number }
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
      change_set?: string | null;
    };

export type IncomingEvent =
  | { type: 'ready'; session: string }
  | { type: 'conversation'; id: string; title: string; transcript: TranscriptItem[] }
  | { type: 'turn_start' }
  | { type: 'turn_end'; seconds: number }
  | { type: 'thinking_delta' | 'text_delta'; text: string }
  | { type: 'tool_start'; id: string; tool: string; label: string }
  | { type: 'tool_end'; id: string; ok: boolean }
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
  | {
      type: 'form_fill';
      form: { type_id: string; mode: 'create' | 'edit'; record_id: string };
      fields: Record<string, unknown>;
      reasoning?: string;
    }
  | { type: 'form_open'; type_id: string; fields: Record<string, unknown>; reasoning?: string }
  | { type: 'error'; message: string };

export type Screen = Record<string, unknown>;

export type OutgoingEvent =
  | { type: 'auth'; token: string }
  | { type: 'open_conversation'; id: string | null }
  | { type: 'screen'; screen: Screen }
  | { type: 'user_message'; text: string }
  | { type: 'confirm'; ids: (number | string)[]; ok: boolean };

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
      // Set once confirmed, when the proposal changed records that can be undone.
      changeSet?: string | null;
      undone?: boolean;
    }
  | { kind: 'system'; id: string; text: string }
  | {
      kind: 'activity';
      id: string;
      steps: Step[];
      // Live turns only: the model's latest reasoning, and when the turn started.
      thinking: string;
      live: boolean;
      startedAt?: number;
      seconds?: number;
    };
