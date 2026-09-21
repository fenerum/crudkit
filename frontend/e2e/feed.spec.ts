import { expect, test } from '@playwright/test';
import { unique } from './helpers';

test('posts a note to an object feed', async ({ page }) => {
  const note = unique('E2E note');
  await page.goto('/AUT2');
  const main = page.getByRole('main');
  await expect(main.getByRole('heading', { name: 'feed items' })).toBeVisible();

  await main.locator('[contenteditable="true"]').first().click();
  await page.keyboard.type(note);
  await main.getByRole('button', { name: 'Post note' }).click();

  await expect(page.getByText('Note posted')).toBeVisible();
  await expect(main.locator('.ck-note-body').filter({ hasText: note })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('main').locator('.ck-note-body').filter({ hasText: note })).toBeVisible();
});
