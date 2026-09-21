import { expect, test } from '@playwright/test';

test('creates, edits and deletes a book', async ({ page }) => {
  const title = `E2E book ${Date.now()}`;

  await page.goto('/BOK');
  await page.getByRole('banner').getByRole('link', { name: /^New/ }).click();
  await page.locator('input[name="title"]').fill(title);
  await page.getByRole('main').getByRole('combobox').fill('Calvino');
  await page.getByRole('option', { name: 'Italo Calvino' }).click();
  await page.getByRole('button', { name: 'Create' }).click();

  // Create honours the list's ?next= and returns there.
  await expect(page).toHaveURL('/BOK');
  await page.getByRole('searchbox', { name: 'Search this view' }).fill(title);
  await expect(page.getByRole('main').getByText('Showing 1–1 of 1')).toBeVisible();
  await page.getByRole('main').getByRole('link', { name: /^BOK\d+$/ }).click();
  await expect(page).toHaveURL(/\/BOK\d+$/);
  const bookUrl = page.url();
  await expect(page.getByRole('main').getByText(title)).toBeVisible();
  await expect(page.getByRole('main').getByRole('link', { name: 'Italo Calvino' })).toBeVisible();

  await page.getByRole('banner').getByRole('link', { name: /^Edit/ }).click();
  const titleInput = page.locator('input[name="title"]');
  await expect(titleInput).toHaveValue(title);
  await titleInput.fill(`${title} (edited)`);
  await page.getByRole('button', { name: 'Save' }).click();

  await expect(page).toHaveURL(bookUrl);
  await expect(page.getByRole('main').getByText(`${title} (edited)`)).toBeVisible();

  await page.goto(`${bookUrl}/delete`);
  await page.getByRole('button', { name: 'Delete' }).click();
  await expect(page).not.toHaveURL(/\/delete$/);
  await page.goto(`/BOK?q=${encodeURIComponent(title)}`);
  await expect(page.getByRole('main').getByText('Nothing here yet')).toBeVisible();
});
