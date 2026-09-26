import { useCallback, useEffect, useRef, useState } from 'react';
import { getAccessToken } from '../data/api';

export type ConnectionState = 'connecting' | 'authenticating' | 'open' | 'closed';

const MIN_BACKOFF = 1000;
const MAX_BACKOFF = 15000;
// Close codes the server uses for terminal failures — reconnecting just hides
// the underlying problem (bad token, missing object).
const DEFAULT_TERMINAL_CLOSE_CODES: ReadonlySet<number> = new Set([4001, 4404]);

export function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}`;
}

// Browsers can't send an Authorization header on the upgrade, so JWT users
// authenticate with a first frame. Read on every (re)connect so a reconnect
// picks up a refreshed token. Session/SAML users have no token and the server
// sends `ready` straight away.
function authFrame() {
  const token = getAccessToken();
  return token ? { type: 'auth', token } : null;
}

type Options<In> = {
  url: string | null;
  onMessage: (msg: In) => void;
  terminalCloseCodes?: ReadonlySet<number>;
  // Stop after this many failed attempts if the server has never sent `ready`
  // (e.g. the route isn't deployed). Once connected, always reconnect.
  maxAttemptsBeforeReady?: number;
};

// A CrudKit socket (see crudkit_api.ws_auth): authenticates, becomes `open` on
// the server's `ready` frame, and reconnects with backoff.
export function useReconnectingSocket<In extends { type: string }, Out = unknown>({
  url,
  onMessage,
  terminalCloseCodes = DEFAULT_TERMINAL_CLOSE_CODES,
  maxAttemptsBeforeReady = Infinity,
}: Options<In>) {
  const [state, setState] = useState<ConnectionState>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(MIN_BACKOFF);
  const reconnectTimerRef = useRef<number | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const terminalCloseCodesRef = useRef(terminalCloseCodes);
  terminalCloseCodesRef.current = terminalCloseCodes;
  const maxAttemptsBeforeReadyRef = useRef(maxAttemptsBeforeReady);
  maxAttemptsBeforeReadyRef.current = maxAttemptsBeforeReady;

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    let everReady = false;
    let failedAttempts = 0;

    const connect = () => {
      if (cancelled) return;
      setState('connecting');
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.addEventListener('open', () => {
        backoffRef.current = MIN_BACKOFF;
        const frame = authFrame();
        if (frame) ws.send(JSON.stringify(frame));
        setState('authenticating');
      });
      ws.addEventListener('message', (event) => {
        try {
          const data = JSON.parse(event.data) as In;
          if (data.type === 'ready') {
            everReady = true;
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
        if (terminalCloseCodesRef.current.has(event.code)) return;
        if (!everReady && ++failedAttempts >= maxAttemptsBeforeReadyRef.current) return;
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

  const send = useCallback((payload: Out) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  }, []);

  return { state, send };
}
