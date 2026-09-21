import { expect, test } from '@playwright/test';
import { unique } from './helpers';

test('shows related books in a tab and creates one prefilled', async ({ page }) => {
  await page.goto('/AUT1');
  const main = page.getByRole('main');
  await main.getByRole('tab', { name: /^books/ }).click();

  await expect(page).toHaveURL(/[?&]tab=inline-BOK/);
  await expect(main.getByText('The Left Hand of Darkness')).toBeVisible();
  await expect(main.getByText('The Dispossessed')).toBeVisible();
  await expect(main.getByText('Kindred')).toBeHidden();

  const title = unique('Inline book');
  await main.getByRole('link', { name: 'New' }).click();
  await expect(page).toHaveURL('/BOK/create?author=AUT1');
  await expect(page.getByRole('main').getByText('Ursula K. Le Guin')).toBeVisible();
  await page.locator('input[name="title"]').fill(title);
  await page.getByRole('button', { name: 'Create' }).click();
  await expect(page).not.toHaveURL(/\/create/);

  await page.goto('/AUT1?tab=inline-BOK');
  await expect(page.getByRole('main').getByText(title)).toBeVisible();
});
