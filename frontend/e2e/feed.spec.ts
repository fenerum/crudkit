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

test('logs a call on an author feed', async ({ page }) => {
  const summary = unique('E2E call');
  await page.goto('/AUT2');
  const composer = page.locator('#feed-form');
  await composer.getByRole('tab', { name: 'Call' }).click();
  await composer.locator('input[name="summary"]').fill(summary);
  await composer.getByRole('button', { name: 'Add call' }).click();

  await expect(page.getByRole('main').locator('.ck-act', { hasText: summary })).toContainText('logged a call');
});

test('sends an email with a file attached from an author feed', async ({ page }) => {
  const subject = unique('E2E email');
  await page.goto('/AUT2');
  const composer = page.locator('#feed-form');
  await composer.getByRole('tab', { name: 'Email' }).click();
  await composer.locator('input[name="to"]').fill('author@example.com');
  await composer.locator('input[name="subject"]').fill(subject);
  await composer.locator('input[type="file"]').setInputFiles({
    name: 'programme.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Doors open at 7pm.'),
  });
  await composer.getByRole('button', { name: 'Send' }).click();

  await expect(page.getByText('Email sent to author@example.com').first()).toBeVisible();
  const row = page.getByRole('main').locator('.ck-act', { hasText: subject });
  await expect(row).toContainText('Sent');
  await expect(row).toContainText('programme.txt');
});
