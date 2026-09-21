import { login } from './helpers';
import { test as setup } from '@playwright/test';

setup('log in as the seeded admin', async ({ page }) => {
  await login(page, 'admin', 'admin');
  await page.waitForURL('/');
  await page.context().storageState({ path: 'e2e/.auth/admin.json' });
});
