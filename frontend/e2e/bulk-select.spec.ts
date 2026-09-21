import { createObject, unique } from './helpers';
import { expect, test } from '@playwright/test';

test('selecting rows shows the bulk bar with a merge link', async ({ page, request }) => {
  const tag = unique('Bulk');
  const books = await Promise.all(
    ['A', 'B', 'C'].map((suffix) => createObject(request, 'BOK', { title: `${tag} ${suffix}`, author: 'AUT2' }))
  );

  await page.goto(`/BOK?q=${encodeURIComponent(tag)}`);
  const main = page.getByRole('main');
  await expect(main.getByText('Showing 1–3 of 3')).toBeVisible();

  await main.getByRole('checkbox', { name: `Select ${books[0].id}` }).check();
  await expect(main.getByText(/\d+ selected/)).toBeHidden();

  await main.getByRole('checkbox', { name: `Select ${books[1].id}` }).check();
  await main.getByRole('checkbox', { name: `Select ${books[2].id}` }).check();
  await expect(main.getByText('3 selected')).toBeVisible();

  await main.getByRole('checkbox', { name: `Select ${books[2].id}` }).uncheck();
  await expect(main.getByText('2 selected')).toBeVisible();
  const merge = main.getByRole('link', { name: 'Merge' });
  await expect(merge).toHaveAttribute('href', `/BOK/merge?object_id=${books[0].id}&object_id=${books[1].id}`);
});
