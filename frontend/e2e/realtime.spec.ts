import { createObject, gotoWithChangeStream, unique, updateObject } from './helpers';
import { expect, test } from '@playwright/test';

// Detail pages don't poll, so seeing the change without a reload or focus
// event means it was pushed over the change stream.
test('an open detail page shows changes made elsewhere', async ({ page, request }) => {
  const name = unique('Realtime');
  const reading = await createObject(request, 'RDG', { name });

  await gotoWithChangeStream(page, `/${reading.id}`);
  await expect(page.getByRole('main').getByText(name)).toBeVisible();

  await updateObject(request, reading.id, { name: `${name} (renamed)` });
  await expect(page.getByRole('main').getByText(`${name} (renamed)`)).toBeVisible();
});

test('the edit form keeps typed values and offers a reload', async ({ page, request }) => {
  const name = unique('Realtime edit');
  const reading = await createObject(request, 'RDG', { name, pages: 100 });

  await gotoWithChangeStream(page, `/${reading.id}/edit`);
  const nameInput = page.locator('input[name="name"]');
  await expect(nameInput).toHaveValue(name);
  await nameInput.fill(`${name} (mine)`);

  await updateObject(request, reading.id, { pages: 200 });
  const banner = page.getByRole('status').filter({ hasText: 'changed elsewhere' });
  await expect(banner).toBeVisible();
  await expect(nameInput).toHaveValue(`${name} (mine)`);

  await banner.getByRole('button', { name: 'Reload' }).click();
  await expect(banner).toBeHidden();
  await expect(nameInput).toHaveValue(name);
  await expect(page.locator('input[name="pages"]')).toHaveValue('200');
});
