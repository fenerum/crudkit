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

export async function createObject(
  request: APIRequestContext,
  type: string,
  data: Record<string, unknown>
): Promise<{ id: string; label: string }> {
  const token = await request.post('/api/v1/token/', {
    data: { username: 'admin', password: 'admin' },
  });
  const { access } = await token.json();
  const response = await request.post(`/api/v1/${type}/`, {
    headers: { Authorization: `Bearer ${access}` },
    data,
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}
