import { useCallback, useEffect, useRef, useState } from 'react';
import type { IncomingEvent, OutgoingEvent } from './types';

export type ConnectionState = 'connecting' | 'authenticating' | 'open' | 'closed';

const MIN_BACKOFF = 1000;
const MAX_BACKOFF = 15000;
// Close codes the server uses for terminal failures — reconnecting just hides
// the underlying problem (bad token, missing object).
const TERMINAL_CLOSE_CODES = new Set([4001, 4404]);

type Options = {
  url: string | null;
  onMessage: (msg: IncomingEvent) => void;
  authFrame?: OutgoingEvent | null;
};

export function useAssistantSocket({ url, onMessage, authFrame }: Options) {
  const [state, setState] = useState<ConnectionState>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(MIN_BACKOFF);
  const reconnectTimerRef = useRef<number | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const authFrameRef = useRef(authFrame);
  authFrameRef.current = authFrame;

  useEffect(() => {
    if (!url) return;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      setState('connecting');
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.addEventListener('open', () => {
        backoffRef.current = MIN_BACKOFF;
        const frame = authFrameRef.current;
        if (frame) {
          ws.send(JSON.stringify(frame));
          setState('authenticating');
        } else {
          // SAML/session users: server sends `ready` immediately.
          setState('authenticating');
        }
      });
      ws.addEventListener('message', (event) => {
        try {
          const data = JSON.parse(event.data) as IncomingEvent;
          if (data.type === 'ready') {
            setState('open');
            return;
          }
          onMessageRef.current(data);
        } catch {
          // ignore malformed
        }
      });
      ws.addEventListener('close', (event) => {
        setState('closed');
        if (cancelled) return;
        if (TERMINAL_CLOSE_CODES.has(event.code)) return;
        const delay = backoffRef.current;
        backoffRef.current = Math.min(MAX_BACKOFF, delay * 2);
        reconnectTimerRef.current = window.setTimeout(connect, delay);
      });
      ws.addEventListener('error', () => {
        ws.close();
      });
    };
    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current != null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [url]);

  const send = useCallback((payload: OutgoingEvent) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  }, []);

  return { state, send };
}
