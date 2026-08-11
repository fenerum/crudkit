import { useEffect, useMemo, useRef, useState, useCallback, KeyboardEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import SafeMarkdown from '../../shared/SafeMarkdown';
import { Icon } from '../ui';
import { useAuth } from '../../context/AuthContext';
import { getAccessToken } from '../../data/api';
import { invalidateModel } from '../../data/invalidate';
import ConfirmCard from './ConfirmCard';
import { useAssistantSocket } from './useAssistantSocket';
import type { ChatItem, IncomingEvent, OutgoingEvent } from './types';

type Props = {
  objectType: string;
  objectId: string;
  onClose: () => void;
};

function buildWsUrl(objectType: string, objectId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const numericId = objectId.replace(/^[A-Z]{3}/, '');
  return `${proto}//${window.location.host}/ws/assistant/${objectType}/${numericId}/`;
}

let _itemSeq = 0;
const nextItemId = () => `item-${++_itemSeq}-${Date.now()}`;

export default function AssistantWindow({ objectType, objectId, onClose }: Props) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const assistantName = user?.assistant?.name || 'Assistant';
  const avatarUrl = user?.assistant?.avatar_url || '';

  const [items, setItems] = useState<ChatItem[]>([]);
  const [input, setInput] = useState('');
  // The backend kicks off a proactive briefing turn as soon as the socket is
  // ready, so we open in the "thinking" state until the first assistant
  // message lands (or an error is shown).
  const [busy, setBusy] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleIncoming = useCallback((evt: IncomingEvent) => {
    if (evt.type === 'assistant_message') {
      setItems((prev) => [...prev, { kind: 'assistant', id: nextItemId(), text: evt.text }]);
      setBusy(false);
    } else if (evt.type === 'tool_call_pending') {
      setItems((prev) => [
        ...prev,
        {
          kind: 'proposal',
          id: evt.id,
          label: evt.label,
          proposalKind: evt.kind,
          payload: evt.payload,
          reasoning: evt.reasoning,
        },
      ]);
    } else if (evt.type === 'tool_outcome') {
      setItems((prev) =>
        prev.map((it) =>
          it.kind === 'proposal' && it.id === evt.id
            ? {
                ...it,
                resolved: evt.ok ? 'confirmed' : evt.status === 'skipped' ? 'skipped' : 'failed',
                summary: evt.summary,
              }
            : it,
        ),
      );
      if (evt.ok) {
        // A confirmed proposal mutated the object the user is looking at.
        // Drop the cached detail/list queries so the page re-fetches.
        invalidateModel(queryClient, objectType);
      }
    } else if (evt.type === 'error') {
      setItems((prev) => [
        ...prev,
        { kind: 'system', id: nextItemId(), text: `Error: ${evt.message}` },
      ]);
      setBusy(false);
    }
  }, [queryClient, objectType]);

  const authFrame = useMemo<OutgoingEvent | null>(() => {
    const token = getAccessToken();
    return token ? { type: 'auth', token } : null;
  }, []);

  const { state, send } = useAssistantSocket({
    url: buildWsUrl(objectType, objectId),
    onMessage: handleIncoming,
    authFrame,
  });

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [items.length]);

  // The server kicks off a proactive briefing as soon as a fresh socket
  // finishes authenticating, so flip back into the "thinking" state on every
  // new connection (covers React StrictMode's double-mount in dev and any
  // mid-session reconnect).
  useEffect(() => {
    if (state === 'authenticating') setBusy(true);
  }, [state]);

  const sendMessage = useCallback(() => {
    const text = input.trim();
    if (!text || state !== 'open') return;
    setItems((prev) => [...prev, { kind: 'user', id: nextItemId(), text }]);
    setInput('');
    setBusy(true);
    send({ type: 'user_message', text });
  }, [input, state, send]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const decide = (proposalId: ChatItem extends { id: infer I } ? I : never, ok: boolean) => {
    send({ type: 'confirm', id: proposalId as any, ok });
    if (ok) setBusy(true);
  };

  return (
    <div
      className="fixed bottom-4 right-4 z-40 w-[380px] max-h-[80vh] flex flex-col rounded-lg shadow-2xl bg-bg-1 border border-bg-4"
      role="dialog"
      aria-label={`${assistantName} chat`}
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-bg-4">
        {avatarUrl ? (
          <img src={avatarUrl} className="w-7 h-7 rounded-full" alt={assistantName} />
        ) : (
          <div
            className="w-7 h-7 rounded-full bg-primary-400 flex items-center justify-center text-white text-xs font-bold"
            aria-hidden="true"
          >
            {assistantName.charAt(0)}
          </div>
        )}
        <div className="flex-1 leading-tight">
          <div className="text-sm font-semibold text-fg-1">{assistantName}</div>
          <div className="text-xs text-fg-3">
            {busy
              ? 'Reading this record…'
              : state === 'open'
                ? 'Ready'
                : state === 'connecting'
                  ? 'Connecting…'
                  : 'Reconnecting…'}
          </div>
        </div>
        <button
          type="button"
          className="ck-btn ck-btn-ghost ck-btn-sm"
          onClick={onClose}
          aria-label="Close"
        >
          <Icon name="x" size={14} color="currentColor" />
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3 text-sm">
        {items.length === 0 && busy && (
          <div className="flex flex-col items-center justify-center gap-2 py-8 text-fg-3">
            <div
              className="w-5 h-5 rounded-full border-2 border-fg-3 border-t-transparent animate-spin"
              aria-hidden="true"
            />
            <div className="text-xs">Reading this record…</div>
          </div>
        )}
        {items.map((it) => {
          if (it.kind === 'user') {
            return (
              <div key={it.id} className="flex justify-end">
                <div className="ck-bubble ck-bubble-out max-w-[80%] whitespace-pre-wrap break-words">
                  {it.text}
                </div>
              </div>
            );
          }
          if (it.kind === 'assistant') {
            return (
              <div key={it.id} className="flex justify-start">
                <div className="ck-bubble ck-bubble-in max-w-[90%]">
                  <SafeMarkdown source={it.text} />
                </div>
              </div>
            );
          }
          if (it.kind === 'system') {
            return (
              <div key={it.id} className="text-xs text-fg-3 italic text-center">
                {it.text}
              </div>
            );
          }
          // proposal
          return (
            <ConfirmCard
              key={`p-${it.id}`}
              label={it.label}
              kind={it.proposalKind}
              payload={it.payload}
              reasoning={it.reasoning}
              resolved={it.resolved}
              summary={it.summary}
              onConfirm={() => decide(it.id, true)}
              onSkip={() => decide(it.id, false)}
            />
          );
        })}
        {busy && <div className="text-xs text-fg-3 italic">Thinking…</div>}
      </div>

      <div className="border-t border-bg-4 p-2">
        <textarea
          className="w-full bg-bg-2 text-fg-1 rounded p-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-400 resize-none"
          rows={2}
          placeholder={state === 'open' ? `Ask ${assistantName}…` : 'Connecting…'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={state !== 'open'}
        />
        <div className="flex justify-between items-center mt-1">
          <div className="text-xs text-fg-3">Enter to send · Shift+Enter for newline</div>
          <button
            type="button"
            className="ck-btn ck-btn-primary ck-btn-sm"
            onClick={sendMessage}
            disabled={state !== 'open' || !input.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
