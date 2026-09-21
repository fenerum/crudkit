import { expect, test } from '@playwright/test';

test('lists the seeded books', async ({ page }) => {
  await page.goto('/BOK');
  const main = page.getByRole('main');
  await expect(main.getByText('The Left Hand of Darkness')).toBeVisible();
  await expect(main.getByText('Parable of the Sower')).toBeVisible();
});

test('search narrows the list', async ({ page }) => {
  await page.goto('/BOK');
  await page.getByRole('searchbox', { name: 'Search this view' }).fill('Kindred');
  await expect(page).toHaveURL(/[?&]q=Kindred/);
  const main = page.getByRole('main');
  await expect(main.getByText('Kindred')).toBeVisible();
  await expect(main.getByText('The Dispossessed')).toBeHidden();
  await expect(main.getByText('Showing 1–1 of 1')).toBeVisible();
});
