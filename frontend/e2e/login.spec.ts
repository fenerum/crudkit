import { expect, test } from '@playwright/test';
import { login } from './helpers';

test.use({ storageState: { cookies: [], origins: [] } });

test('rejects a wrong password', async ({ page }) => {
  await login(page, 'admin', 'wrong');
  await expect(page.getByRole('alert')).toHaveText('Invalid username or password');
  await expect(page).toHaveURL('/login');
});

test('redirects a deep link to the login form', async ({ page }) => {
  await page.goto('/BOK');
  await expect(page).toHaveURL('/login');
});

test('signs in and lands on the dashboard', async ({ page }) => {
  await login(page, 'admin', 'admin');
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('link', { name: /admin@example\.com/ })).toBeVisible();
});
