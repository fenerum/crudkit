import { expect, test } from '@playwright/test';
import { createObject, unique } from './helpers';

test('an edit can be reverted from the History tab', async ({ page, request }) => {
  const name = unique('History');
  const reading = await createObject(request, 'RDG', { name });

  await page.goto(`/${reading.id}/edit`);
  const nameInput = page.locator('input[name="name"]');
  await expect(nameInput).toHaveValue(name);
  await nameInput.fill(`${name} (edited)`);
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('main').getByText(`${name} (edited)`)).toBeVisible();

  await page.getByRole('tab', { name: 'History' }).click();
  await expect(page).toHaveURL(`/${reading.id}?tab=history`);
  const edit = page.getByTestId('history-batch').first();
  await expect(edit.getByText('You')).toBeVisible();
  await edit.getByRole('button', { name: 'Revert' }).click();

  await expect(page.getByTestId('history-batch').first().getByText('Undo')).toBeVisible();
  await page.goto(`/${reading.id}`);
  await expect(page.getByRole('main').getByText(name, { exact: true })).toBeVisible();
});

test('a delete can be undone from the toast, and a deleted record restored', async ({ page, request }) => {
  const name = unique('Undo');
  const reading = await createObject(request, 'RDG', { name });

  await page.goto(`/${reading.id}/delete`);
  await expect(page.getByText('You can restore it from History.')).toBeVisible();
  await page.getByRole('button', { name: 'Delete' }).click();
  await page.getByRole('alert').getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(page).toHaveURL(`/${reading.id}`);
  await expect(page.getByRole('status').filter({ hasText: 'was deleted' })).toHaveCount(0);

  await page.goto(`/${reading.id}/delete`);
  await page.getByRole('button', { name: 'Delete' }).click();
  await page.goto(`/${reading.id}`);
  const banner = page.getByRole('status').filter({ hasText: 'This record was deleted.' });
  await banner.getByRole('button', { name: 'Restore' }).click();
  await expect(banner).toHaveCount(0);
});
