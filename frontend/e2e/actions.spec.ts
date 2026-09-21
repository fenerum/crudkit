import { createObject, unique } from './helpers';
import { expect, test } from '@playwright/test';

test('runs a model action from the detail menu', async ({ page, request }) => {
  const name = unique('Action');
  const reading = await createObject(request, 'RDG', { name });

  await page.goto(`/${reading.id}`);
  // Choice fields render their label, not the stored value.
  await expect(page.getByRole('main').getByText('To read', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /^Actions/ }).click();
  page.once('dialog', (dialog) => {
    expect(dialog.message()).toBe('Are you sure you want to mark finished?');
    dialog.accept();
  });
  await page.getByRole('menuitem', { name: /^Mark finished/ }).click();

  await expect(page.getByText(`${name} marked finished`)).toBeVisible();
  await page.reload();
  await expect(page.getByRole('main').getByText('Finished', { exact: true })).toBeVisible();
});

test('lists only the list-page menu entries on a list', async ({ page }) => {
  await page.goto('/RDG');
  await page.getByRole('button', { name: /^Actions/ }).click();
  await expect(page.getByRole('menuitem', { name: /Edit view/ })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: /Mark finished/ })).toBeHidden();
});
