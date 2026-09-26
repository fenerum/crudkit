// Server-pushed change hints (crudkit_api.consumers.ChangesConsumer). Each hint
// only names the changed model/id; we invalidate the matching queries and let
// React Query refetch through the permission-checked REST API. While the socket
// is down, callers fall back to polling and focus refetches.
import { createContext, ReactNode, useCallback, useContext, useEffect, useRef } from 'react';
import { QueryClient, useQueryClient } from '@tanstack/react-query';
import { invalidateModel } from './invalidate';
import { useReconnectingSocket, wsUrl } from '../hooks/useReconnectingSocket';

export type ChangeEvent = {
  type: 'change';
  model: string;
  // Omitted for deletes: the server can no longer check row permissions.
  id: number | null;
  action: 'saved' | 'deleted';
  by: number | null;
};

// Coalesces bursts (bulk imports, cascades) into one invalidation per model.
const BATCH_MS = 300;
// The server closes with 4503 when it has no channel layer: nothing will ever
// be pushed, so stop retrying and keep polling. 4001 is retried because a
// reconnect re-reads the (possibly refreshed) access token.
const TERMINAL_CLOSE_CODES: ReadonlySet<number> = new Set([4503]);
// Projects that haven't routed ws/changes/ (WSGI, or ASGI without
// crudkit_api.routing) never send `ready`; give up and keep polling.
const MAX_ATTEMPTS_BEFORE_READY = 3;

let connected = false;
export const isRealtimeConnected = () => connected;

const RealtimeContext = createContext(false);
export const useRealtimeConnected = () => useContext(RealtimeContext);

export function invalidateChangedModels(qc: QueryClient, models: Iterable<string>) {
  for (const model of models) {
    invalidateModel(qc, model);
    qc.invalidateQueries({ queryKey: ['inline-count', model] });
    qc.invalidateQueries({ queryKey: ['inline-list', model] });
    qc.invalidateQueries({ queryKey: ['inline-feed', model] });
    // Saved-view and layout queries are keyed by their target model, which
    // the hint doesn't carry.
    if (model === 'VIW') {
      qc.invalidateQueries({ queryKey: ['view'] });
      qc.invalidateQueries({ queryKey: ['views'] });
    }
    if (model === 'LAY') qc.invalidateQueries({ queryKey: ['layouts'] });
    if (model === 'WLG') qc.invalidateQueries({ queryKey: ['activeWorkLog'] });
  }
  qc.invalidateQueries({ queryKey: ['widgets'] });
}

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const pendingModels = useRef(new Set<string>());
  const flushTimer = useRef<number | null>(null);

  const onMessage = useCallback(
    (msg: ChangeEvent) => {
      if (msg.type !== 'change') return;
      pendingModels.current.add(msg.model);
      if (flushTimer.current != null) return;
      flushTimer.current = window.setTimeout(() => {
        flushTimer.current = null;
        const models = [...pendingModels.current];
        pendingModels.current.clear();
        invalidateChangedModels(qc, models);
      }, BATCH_MS);
    },
    [qc],
  );

  const { state } = useReconnectingSocket<ChangeEvent>({
    url: wsUrl('/ws/changes/'),
    onMessage,
    terminalCloseCodes: TERMINAL_CLOSE_CODES,
    maxAttemptsBeforeReady: MAX_ATTEMPTS_BEFORE_READY,
  });
  const isOpen = state === 'open';

  const wasOpen = useRef(false);
  useEffect(() => {
    connected = isOpen;
    if (!isOpen) return;
    // Changes made while we were disconnected were never pushed.
    if (wasOpen.current) qc.invalidateQueries();
    wasOpen.current = true;
  }, [isOpen, qc]);

  useEffect(
    () => () => {
      connected = false;
      if (flushTimer.current != null) window.clearTimeout(flushTimer.current);
    },
    [],
  );

  return <RealtimeContext.Provider value={isOpen}>{children}</RealtimeContext.Provider>;
}
