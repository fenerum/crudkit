import { expect, test } from '@playwright/test';

test('pages through a list with Next and Previous', async ({ page }) => {
  await page.goto('/AUT?page_size=1');
  const main = page.getByRole('main');
  await expect(main.getByText('Showing 1–1 of 3')).toBeVisible();
  await expect(main.getByRole('button', { name: 'Previous' })).toBeDisabled();

  await main.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/[?&]page=2/);
  await expect(main.getByText('Showing 2–2 of 3')).toBeVisible();
  await expect(main.getByRole('button', { name: '2', exact: true })).toHaveAttribute('aria-current', 'page');

  await main.getByRole('button', { name: '3', exact: true }).click();
  await expect(main.getByText('Showing 3–3 of 3')).toBeVisible();
  await expect(main.getByRole('button', { name: 'Next' })).toBeDisabled();

  await main.getByRole('button', { name: 'Previous' }).click();
  await expect(main.getByText('Showing 2–2 of 3')).toBeVisible();
});

test('remembers the chosen page size', async ({ page }) => {
  await page.goto('/RDG');
  const main = page.getByRole('main');
  await main.getByRole('navigation', { name: 'Pagination' }).getByText('50 / page').click();
  await page.getByRole('option', { name: '10 / page' }).click();

  await expect(page).toHaveURL(/[?&]page_size=10/);
  await expect(main.getByText(/^Showing 1–10 of \d+$/)).toBeVisible();

  await page.goto('/RDG');
  await expect(main.getByText(/^Showing 1–10 of \d+$/)).toBeVisible();
});
