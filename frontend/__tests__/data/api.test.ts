import { beforeEach, describe, expect, it, vi } from 'vitest';

import CrudKitAPIClient from '../../data/api';


describe('CrudKitAPIClient.logout', () => {
  beforeEach(() => {
    localStorage.clear();
    document.head.innerHTML = '<meta name="csrf-token" content="csrf">';
  });

  it('notifies the server before clearing local tokens', async () => {
    const request = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', request);
    const client = new CrudKitAPIClient();
    client.storeTokens('access', 'refresh');

    await client.logout();

    expect(request).toHaveBeenCalledWith(
      '/api/v1/logout/',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ refresh: 'refresh' }),
      }),
    );
    expect(client.getAccessToken()).toBeNull();
    expect(client.getRefreshToken()).toBeNull();
  });

  it('clears local tokens when the server is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const client = new CrudKitAPIClient();
    client.storeTokens('access', 'refresh');

    await client.logout();

    expect(client.getAccessToken()).toBeNull();
    expect(client.getRefreshToken()).toBeNull();
  });
});
