import { KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import SafeMarkdown from '../../shared/SafeMarkdown';
import { Icon, useScreen } from '../ui';
import { useAuth } from '../../context/AuthContext';
import { invalidateObject } from '../../data/invalidate';
import ActivityBlock from './ActivityBlock';
import ConfirmCard from './ConfirmCard';
import { useReconnectingSocket, wsUrl } from '../../hooks/useReconnectingSocket';
import type { ChatItem, IncomingEvent, OutgoingEvent, Resolution, Screen, TranscriptItem } from './types';

type Props = {
  onClose: () => void;
};

const CONVERSATION_KEY = 'crudkit.assistant.conversation';
const SCREEN_DEBOUNCE_MS = 300;

let _itemSeq = 0;
const nextItemId = () => `item-${++_itemSeq}-${Date.now()}`;

function resolutionOf(status: string): Resolution | undefined {
  return status === 'confirmed' || status === 'skipped' || status === 'failed' ? status : undefined;
}

export function fromTranscript(transcript: TranscriptItem[]): ChatItem[] {
  return transcript.map((item) =>
    item.role === 'activity'
      ? { kind: 'activity', id: nextItemId(), steps: item.steps, thinking: '', live: false, seconds: item.seconds }
      : item.role === 'proposal'
      ? {
          kind: 'proposal',
          id: item.id,
          label: item.label,
          proposalKind: item.kind,
          payload: item.payload,
          reasoning: item.reasoning,
          target: item.target,
          targetLabel: item.target_label,
          resolved: resolutionOf(item.status),
          summary: item.summary,
        }
      : { kind: item.role, id: nextItemId(), text: item.text },
  );
}

export function screenLabel(screen: Screen): string {
  const selected = (screen.selected_ids as string[] | undefined)?.length;
  switch (screen.route) {
    case 'detail':
      return `${screen.record_id}${screen.tab ? ` · ${screen.tab}` : ''}`;
    case 'list':
      return [
        `${screen.type_id} list`,
        screen.view_id,
        screen.q ? `“${screen.q}”` : null,
        selected ? `${selected} selected` : null,
      ]
        .filter(Boolean)
        .join(' · ');
    case 'dashboard':
      return 'Dashboard';
    case 'inbox':
      return 'Inbox';
    default:
      return String(screen.path || '');
  }
}

export function suggestionsFor(screen: Screen): string[] {
  if (screen.route === 'detail') return ['Summarize this record', 'What changed recently?', 'What should happen next?'];
  if (screen.route === 'list') {
    return (screen.selected_ids as string[] | undefined)?.length
      ? ['Summarize the selected rows', 'What do the selected rows have in common?']
      : ['What stands out in this list?', 'Summarize what is on screen'];
  }
  return ['What needs my attention?'];
}

export default function AssistantSidebar({ onClose }: Props) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const screen = useScreen() as Screen;
  const assistantName = user?.assistant?.name || 'Assistant';
  const avatarUrl = user?.assistant?.avatar_url || '';

  const [items, setItems] = useState<ChatItem[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  // The reply as it streams in, until the final assistant_message replaces it.
  const [draft, setDraft] = useState('');
  // Proposals whose Confirm/Skip was sent and whose outcome hasn't arrived yet.
  const [deciding, setDeciding] = useState<Map<number | string, 'confirm' | 'skip'>>(new Map());
  const scrollRef = useRef<HTMLDivElement>(null);
  // Proposal id → target CK-ID, so a confirmed outcome can refresh that record.
  const targetsRef = useRef(new Map<number | string, string>());

  // Apply `update` to the activity item of the turn in progress.
  const updateLiveActivity = useCallback(
    (update: (item: Extract<ChatItem, { kind: 'activity' }>) => Partial<Extract<ChatItem, { kind: 'activity' }>>) =>
      setItems((prev) => prev.map((it) => (it.kind === 'activity' && it.live ? { ...it, ...update(it) } : it))),
    [],
  );

  const handleIncoming = useCallback(
    (evt: IncomingEvent) => {
      if (evt.type === 'turn_start') {
        setBusy(true);
        setDraft('');
        setItems((prev) => [
          ...prev,
          { kind: 'activity', id: nextItemId(), steps: [], thinking: '', live: true, startedAt: Date.now() },
        ]);
      } else if (evt.type === 'thinking_delta') {
        updateLiveActivity((it) => ({ thinking: it.thinking + evt.text }));
      } else if (evt.type === 'text_delta') {
        setDraft((prev) => prev + evt.text);
      } else if (evt.type === 'tool_start') {
        // Text written before a tool call is the model narrating; the step replaces it.
        setDraft('');
        updateLiveActivity((it) => ({ thinking: '', steps: [...it.steps, { id: evt.id, label: evt.label, ok: null }] }));
      } else if (evt.type === 'tool_end') {
        updateLiveActivity((it) => ({
          steps: it.steps.map((step) => (step.id === evt.id ? { ...step, ok: evt.ok } : step)),
        }));
      } else if (evt.type === 'turn_end') {
        setBusy(false);
        setDraft('');
        // Keep the finished turn's steps as a summary; a turn without tool calls leaves nothing.
        setItems((prev) =>
          prev.flatMap((it) =>
            it.kind === 'activity' && it.live
              ? it.steps.length
                ? [{ ...it, live: false, thinking: '', seconds: evt.seconds }]
                : []
              : [it],
          ),
        );
      } else if (evt.type === 'conversation') {
        localStorage.setItem(CONVERSATION_KEY, evt.id);
        const restored = fromTranscript(evt.transcript);
        restored.forEach((it) => it.kind === 'proposal' && it.target && targetsRef.current.set(it.id, it.target));
        setItems(restored);
        setBusy(false);
      } else if (evt.type === 'assistant_message') {
        setDraft('');
        setItems((prev) => [...prev, { kind: 'assistant', id: nextItemId(), text: evt.text }]);
      } else if (evt.type === 'tool_call_pending') {
        if (evt.target) targetsRef.current.set(evt.id, evt.target);
        setItems((prev) => [
          ...prev,
          {
            kind: 'proposal',
            id: evt.id,
            label: evt.label,
            proposalKind: evt.kind,
            payload: evt.payload,
            reasoning: evt.reasoning,
            target: evt.target,
            targetLabel: evt.target_label,
          },
        ]);
      } else if (evt.type === 'tool_outcome') {
        setItems((prev) =>
          prev.map((it) =>
            it.kind === 'proposal' && it.id === evt.id
              ? { ...it, resolved: evt.ok ? 'confirmed' : resolutionOf(evt.status) || 'failed', summary: evt.summary }
              : it,
          ),
        );
        setDeciding((prev) => new Map([...prev].filter(([id]) => id !== evt.id)));
        const target = targetsRef.current.get(evt.id);
        if (evt.ok && target) invalidateObject(queryClient, target);
      } else if (evt.type === 'error') {
        setItems((prev) => [...prev, { kind: 'system', id: nextItemId(), text: `Error: ${evt.message}` }]);
        setBusy(false);
        setDeciding(new Map());
      }
    },
    [queryClient, updateLiveActivity],
  );

  const url = useMemo(() => wsUrl('/ws/assistant/'), []);
  const { state, send } = useReconnectingSocket<IncomingEvent, OutgoingEvent>({ url, onMessage: handleIncoming });

  // (Re)open the stored conversation whenever a socket becomes ready.
  useEffect(() => {
    if (state === 'open') send({ type: 'open_conversation', id: localStorage.getItem(CONVERSATION_KEY) });
  }, [state, send]);

  const screenJson = JSON.stringify(screen);
  useEffect(() => {
    if (state !== 'open') return;
    const timer = window.setTimeout(
      () => send({ type: 'screen', screen: JSON.parse(screenJson) }),
      SCREEN_DEBOUNCE_MS,
    );
    return () => window.clearTimeout(timer);
  }, [screenJson, state, send]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [items, draft]);

  const ask = useCallback(
    (text: string) => {
      text = text.trim();
      if (!text || state !== 'open') return;
      setItems((prev) => [...prev, { kind: 'user', id: nextItemId(), text }]);
      setInput('');
      setBusy(true);
      // Send the screen right away so the turn never sees a debounced, stale one.
      send({ type: 'screen', screen: JSON.parse(screenJson) });
      send({ type: 'user_message', text });
    },
    [state, send, screenJson],
  );

  const newChat = () => {
    localStorage.removeItem(CONVERSATION_KEY);
    targetsRef.current.clear();
    setItems([]);
    send({ type: 'open_conversation', id: null });
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      ask(input);
    }
  };

  // Applied right away by the server, without a model turn — even mid-turn.
  const decide = (proposalIds: (number | string)[], ok: boolean) => {
    send({ type: 'confirm', ids: proposalIds, ok });
    setDeciding((prev) => new Map([...prev, ...proposalIds.map((id) => [id, ok ? 'confirm' : 'skip'] as const)]));
  };

  const pendingIds = items.flatMap((it) =>
    it.kind === 'proposal' && !it.resolved && !deciding.has(it.id) ? [it.id] : [],
  );

  return (
    <aside className="flex flex-col h-full bg-bg-1" aria-label={`${assistantName} chat`}>
      <div className="flex items-center gap-2 px-3 border-b border-border-1" style={{ height: 'var(--topbar-h)' }}>
        {avatarUrl ? (
          <img src={avatarUrl} className="w-6 h-6 rounded-full" alt={assistantName} />
        ) : (
          <div
            className="w-6 h-6 rounded-full bg-primary-400 flex items-center justify-center text-white text-xs font-bold"
            aria-hidden="true"
          >
            {assistantName.charAt(0)}
          </div>
        )}
        <div className="flex-1 leading-tight min-w-0">
          <div className="text-sm font-semibold text-fg-1">{assistantName}</div>
          <div className="text-2xs text-fg-3">
            {busy ? 'Working…' : state === 'open' ? 'Ready' : state === 'connecting' ? 'Connecting…' : 'Reconnecting…'}
          </div>
        </div>
        <button
          type="button"
          className="ck-icon-btn ck-icon-btn-sm"
          onClick={newChat}
          disabled={state !== 'open' || busy}
          aria-label="New chat"
          title="New chat"
        >
          <Icon name="plus" size={14} color="currentColor" />
        </button>
        <button type="button" className="ck-icon-btn ck-icon-btn-sm" onClick={onClose} aria-label="Close assistant">
          <Icon name="x" size={14} color="currentColor" />
        </button>
      </div>

      <div
        className="flex items-center gap-1.5 px-3 py-1.5 border-b border-border-1 text-2xs text-fg-3"
        data-testid="assistant-screen"
      >
        <Icon name="eye" size={12} color="currentColor" />
        <span className="truncate">{screenLabel(screen)}</span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3 text-sm">
        {items.length === 0 && !busy && (
          <div className="flex flex-col gap-2 pt-2">
            <div className="text-xs text-fg-3">Ask about what you are looking at, or try:</div>
            {suggestionsFor(screen).map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="ck-btn ck-btn-secondary ck-btn-sm justify-start text-left"
                onClick={() => ask(suggestion)}
                disabled={state !== 'open'}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
        {items.map((it) => {
          if (it.kind === 'user') {
            return (
              <div key={it.id} className="flex justify-end">
                <div className="ck-bubble ck-bubble-out max-w-[85%] whitespace-pre-wrap break-words">{it.text}</div>
              </div>
            );
          }
          if (it.kind === 'assistant') {
            return (
              <div key={it.id} className="flex justify-start">
                <div className="ck-bubble ck-bubble-in max-w-[95%]">
                  <SafeMarkdown source={it.text} />
                </div>
              </div>
            );
          }
          if (it.kind === 'activity') {
            return (
              <ActivityBlock
                key={it.id}
                steps={it.steps}
                thinking={it.thinking}
                live={it.live}
                startedAt={it.startedAt}
                seconds={it.seconds}
              />
            );
          }
          if (it.kind === 'system') {
            return (
              <div key={it.id} className="text-xs text-fg-3 italic text-center">
                {it.text}
              </div>
            );
          }
          return (
            <ConfirmCard
              key={`p-${it.id}`}
              label={it.label}
              kind={it.proposalKind}
              payload={it.payload}
              reasoning={it.reasoning}
              target={it.target}
              targetLabel={it.targetLabel}
              resolved={it.resolved}
              summary={it.summary}
              deciding={deciding.get(it.id)}
              onConfirm={() => decide([it.id], true)}
              onSkip={() => decide([it.id], false)}
            />
          );
        })}
        {draft && (
          <div className="flex justify-start">
            <div className="ck-bubble ck-bubble-in max-w-[95%]" data-testid="assistant-draft">
              <SafeMarkdown source={draft} />
            </div>
          </div>
        )}
      </div>

      {pendingIds.length > 1 && (
        <div className="flex items-center gap-2 px-3 py-2 border-t border-border-1 text-xs text-fg-2">
          <span className="flex-1">{pendingIds.length} changes waiting</span>
          <button type="button" className="ck-btn ck-btn-primary ck-btn-sm" onClick={() => decide(pendingIds, true)}>
            Confirm all
          </button>
          <button type="button" className="ck-btn ck-btn-secondary ck-btn-sm" onClick={() => decide(pendingIds, false)}>
            Skip all
          </button>
        </div>
      )}

      <div className="border-t border-border-1 p-2">
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
          <div className="text-2xs text-fg-3">Enter to send · Shift+Enter for newline</div>
          <button
            type="button"
            className="ck-btn ck-btn-primary ck-btn-sm"
            onClick={() => ask(input)}
            disabled={state !== 'open' || !input.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </aside>
  );
}
