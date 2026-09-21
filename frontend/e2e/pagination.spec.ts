import { expect, test } from '@playwright/test';

test('pages through a list with Next and Previous', async ({ page }) => {
  // Other specs create Authors in the shared DB, so read the total instead of
  // assuming the seeded count.
  await page.goto('/AUT?page_size=1');
  const main = page.getByRole('main');
  const showing = main.getByText(/^Showing 1–1 of \d+$/);
  await expect(showing).toBeVisible();
  const total = Number((await showing.textContent())!.match(/of (\d+)/)![1]);
  expect(total).toBeGreaterThanOrEqual(3);
  await expect(main.getByRole('button', { name: 'Previous' })).toBeDisabled();

  await main.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/[?&]page=2/);
  await expect(main.getByText(`Showing 2–2 of ${total}`)).toBeVisible();
  await expect(main.getByRole('button', { name: '2', exact: true })).toHaveAttribute('aria-current', 'page');

  await main.getByRole('button', { name: '3', exact: true }).click();
  await expect(main.getByText(`Showing 3–3 of ${total}`)).toBeVisible();

  await main.getByRole('button', { name: 'Previous' }).click();
  await expect(main.getByText(`Showing 2–2 of ${total}`)).toBeVisible();

  await page.goto(`/AUT?page_size=1&page=${total}`);
  await expect(main.getByText(`Showing ${total}–${total} of ${total}`)).toBeVisible();
  await expect(main.getByRole('button', { name: 'Next' })).toBeDisabled();
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
