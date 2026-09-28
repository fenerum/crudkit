import { expect, test } from '@playwright/test';
import { createObject, unique } from './helpers';

test('confirming a pending proposal in the inbox changes the record', async ({ page, request }) => {
  const name = unique('Proposal reading');
  const renamed = `${name} renamed`;
  const reading = await createObject(request, 'RDG', { name });
  // The admin user files it, as an MCP client acting for them would.
  await createObject(request, 'ASP', { target: reading.id, kind: 'patch', payload: { fields: { name: renamed } } });

  await page.goto('/inbox?tab=proposals');
  const row = page
    .getByTestId('proposal')
    .filter({ has: page.getByRole('link', { name: reading.id, exact: true }) });
  await expect(row.getByText(`name = "${renamed}"`)).toBeVisible();
  await row.getByRole('button', { name: 'Confirm' }).click();
  await expect(row).toHaveCount(0);

  await page.goto(`/${reading.id}`);
  await expect(page.getByRole('main').getByText(renamed).first()).toBeVisible();
});

test('actions that need approval carry a shield', async ({ page, request }) => {
  const reading = await createObject(request, 'RDG', { name: unique('Shield reading') });
  await page.goto(`/${reading.id}`);
  await page.getByRole('button', { name: /^Actions/ }).click();
  await expect(page.getByRole('menuitem', { name: /^Mark finished/ })).toHaveAttribute(
    'title',
    'Connected apps and agents need your approval to run this'
  );
});
