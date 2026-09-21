import { expect, test } from '@playwright/test';

test('opens a book from the list and follows its author link', async ({ page }) => {
  await page.goto('/BOK?q=Kindred');
  await page.getByRole('main').getByRole('link', { name: /^BOK\d+$/ }).click();

  const main = page.getByRole('main');
  await expect(main.getByText('Jun 1, 1979')).toBeVisible();
  await main.getByRole('link', { name: 'Octavia E. Butler' }).click();

  await expect(page).toHaveURL(/\/AUT\d+$/);
  await expect(page.getByRole('banner').getByText('Octavia E. Butler')).toBeVisible();
});
