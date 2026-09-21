import { type Page, expect, test } from '@playwright/test';

// One active work log per user: this is the only spec that starts a timer,
// and it always leaves none running so a failed run can't poison the next.
async function stopRunningTimer(page: Page) {
  await page.goto('/RDG');
  const banner = page.getByRole('banner');
  const stop = banner.getByRole('button', { name: 'Stop time tracking' });
  await expect(stop.or(banner.getByRole('button', { name: 'Start' }))).toBeVisible();
  if (await stop.isVisible()) {
    await stop.click();
    await expect(page.getByText('Time tracking stopped')).toBeVisible();
  }
}

test.beforeEach(({ page }) => stopRunningTimer(page));
test.afterEach(({ page }) => stopRunningTimer(page));

test('starts and stops time tracking on an object', async ({ page }) => {
  const banner = page.getByRole('banner');
  await expect(banner.getByRole('button', { name: 'Start' })).toBeDisabled();

  await page.goto('/RDG1');
  await banner.getByRole('button', { name: 'Start' }).click();
  await expect(page.getByText('Time tracking started')).toBeVisible();
  await expect(banner.getByRole('button', { name: 'Stop time tracking' })).toBeVisible();
  await expect(banner.getByText(/^\d+:\d\d$/)).toBeVisible();

  // The running timer follows the user around.
  await page.goto('/AUT1');
  await expect(banner.getByRole('link', { name: 'RDG1', exact: true })).toBeVisible();

  await banner.getByRole('button', { name: 'Stop time tracking' }).click();
  await expect(page.getByText('Time tracking stopped')).toBeVisible();
  await expect(banner.getByRole('button', { name: 'Start' })).toBeVisible();
});
