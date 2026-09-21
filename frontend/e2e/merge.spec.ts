import { createObject, unique } from './helpers';
import { expect, test } from '@playwright/test';

test('merges two books, keeping a value from the second', async ({ page, request }) => {
  const tag = unique('Merge');
  const first = await createObject(request, 'BOK', { title: `${tag} first`, author: 'AUT2' });
  const second = await createObject(request, 'BOK', { title: `${tag} second`, author: 'AUT2' });

  await page.goto(`/BOK?q=${encodeURIComponent(tag)}`);
  const main = page.getByRole('main');
  await main.getByRole('checkbox', { name: `Select ${first.id}` }).check();
  await main.getByRole('checkbox', { name: `Select ${second.id}` }).check();
  await main.getByRole('link', { name: 'Merge' }).click();

  await expect(page.getByRole('heading', { name: 'Merge 2 records' })).toBeVisible();
  await expect(page.getByRole('radio', { name: first.id })).toBeChecked();
  await page.getByRole('radio', { name: `${tag} second` }).check();
  await page.getByRole('button', { name: 'Merge records' }).click();

  await expect(page).toHaveURL(`/${first.id}`);
  await expect(page.getByRole('main').getByText(`${tag} second`)).toBeVisible();

  await page.goto(`/BOK?q=${encodeURIComponent(tag)}`);
  await expect(page.getByRole('main').getByText('Showing 1–1 of 1')).toBeVisible();
  await expect(page.getByRole('main').getByRole('link', { name: second.id, exact: true })).toBeHidden();
});
