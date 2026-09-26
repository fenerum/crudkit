import { createObject, unique } from './helpers';
import { expect, test } from '@playwright/test';

const palette = (page) => page.getByRole('textbox', { name: 'Search objects, navigate, or run actions…' });

test('finds objects across models and opens the chosen one', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /^Search/ }).click();
  await palette(page).fill('Kindred');

  const results = page.locator('.ck-cmd-item');
  await expect(results.filter({ hasText: 'Kindred audiobook' })).toBeVisible();
  await results.filter({ hasText: 'Book club: Kindred' }).click();

  await expect(page).toHaveURL(/\/RDG\d+$/);
  await expect(page.getByRole('banner').getByText('Book club: Kindred')).toBeVisible();
});

test('offers "Show all" when a type has more results than shown', async ({ page, request }) => {
  const tag = unique('Overflow');
  for (let i = 0; i < 6; i++) {
    await createObject(request, 'RDG', { name: `${tag} ${i}` });
  }

  await page.goto('/');
  await page.getByRole('button', { name: /^Search/ }).click();
  await palette(page).fill(tag);

  const results = page.locator('.ck-cmd-item');
  await expect(page.locator('.ck-cmd .eyebrow', { hasText: 'readings (RDG)' })).toBeVisible();
  await expect(results.filter({ hasText: tag })).toHaveCount(5);
  await results.filter({ hasText: 'Show all readings' }).click();

  await expect(page).toHaveURL(`/RDG?q=${encodeURIComponent(tag)}`);
  await expect(page.getByText(`${tag} 5`)).toBeVisible();
});

test('opens with the keyboard shortcut and closes with Escape', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('link', { name: /admin@example\.com/ })).toBeVisible();
  await page.keyboard.press('ControlOrMeta+k');
  await expect(palette(page)).toBeFocused();
  await palette(page).fill('zzz-no-such-thing');
  await expect(page.getByText('No matches')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(palette(page)).toBeHidden();
});
