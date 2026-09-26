import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useReconnectingSocket } from '../../hooks/useReconnectingSocket';

class FakeSocket extends EventTarget {
  static instances: FakeSocket[] = [];
  static OPEN = 1;
  readyState = 0;
  constructor(public url: string) {
    super();
    FakeSocket.instances.push(this);
  }
  send() {}
  close() {}
  serverSends(data: object) {
    this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(data) }));
  }
  serverCloses(code = 1006) {
    this.dispatchEvent(new CloseEvent('close', { code }));
  }
}

function failAndWait() {
  act(() => FakeSocket.instances.at(-1)!.serverCloses());
  act(() => vi.advanceTimersByTime(20_000));
}

describe('useReconnectingSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  test('gives up when the server never becomes ready', () => {
    renderHook(() => useReconnectingSocket({ url: 'ws://x/', onMessage: () => {}, maxAttemptsBeforeReady: 3 }));
    failAndWait();
    failAndWait();
    failAndWait();
    expect(FakeSocket.instances).toHaveLength(3);
  });

  test('keeps reconnecting once it has been ready', () => {
    renderHook(() => useReconnectingSocket({ url: 'ws://x/', onMessage: () => {}, maxAttemptsBeforeReady: 3 }));
    act(() => FakeSocket.instances[0].serverSends({ type: 'ready' }));
    failAndWait();
    failAndWait();
    failAndWait();
    expect(FakeSocket.instances).toHaveLength(4);
  });
});
