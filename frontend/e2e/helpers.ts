import { type APIRequestContext, type Page, expect } from '@playwright/test';

export async function login(page: Page, username: string, password: string) {
  await page.goto('/login');
  await page.getByPlaceholder('Username').fill(username);
  await page.getByPlaceholder('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

// Tests share one seeded DB and run in parallel, so each creates its own
// records with a unique marker instead of mutating seeded rows.
export function unique(prefix: string) {
  return `${prefix} ${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
}

async function authHeaders(request: APIRequestContext) {
  const token = await request.post('/api/v1/token/', {
    data: { username: 'admin', password: 'admin' },
  });
  const { access } = await token.json();
  return { Authorization: `Bearer ${access}` };
}

export async function createObject(
  request: APIRequestContext,
  type: string,
  data: Record<string, unknown>
): Promise<{ id: string; label: string }> {
  const response = await request.post(`/api/v1/${type}/`, {
    headers: await authHeaders(request),
    data,
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

// `id` is the CK-ID (e.g. "RDG12"), as returned by createObject.
export async function updateObject(request: APIRequestContext, id: string, data: Record<string, unknown>) {
  const response = await request.patch(`/api/v1/${id.slice(0, 3)}/${id.slice(3)}/`, {
    headers: await authHeaders(request),
    data,
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

// Navigates and waits until the change stream has joined its groups, so a
// change made right after is guaranteed to be pushed to this page.
export async function gotoWithChangeStream(page: Page, url: string) {
  const ready = page
    .waitForEvent('websocket', (ws) => ws.url().endsWith('/ws/changes/'))
    .then((ws) => ws.waitForEvent('framereceived', (frame) => String(frame.payload).includes('"ready"')));
  await page.goto(url);
  await ready;
}
