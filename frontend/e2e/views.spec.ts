import { createObject, unique } from './helpers';
import { expect, test } from '@playwright/test';

test('creates a filtered saved view and switches to it', async ({ page }) => {
  const name = unique('Finished high');
  await page.goto('/VIW/create?model=RDG&next=/RDG');
  await page.locator('input[name="name"]').fill(name);
  await page
    .locator('textarea[name="filters"]')
    .fill('[["status", "=", "finished"], ["priority", "=", "high"]]');
  await page.getByRole('main').getByRole('button', { name: 'Create', exact: true }).click();

  await expect(page).toHaveURL('/RDG');
  await page.getByRole('banner').getByRole('button', { name }).click();
  await expect(page).toHaveURL(/\/RDG\/VIW\/VIW\d+$/);

  const main = page.getByRole('main');
  await expect(main.getByText('Book club: Kindred')).toBeVisible();
  await expect(main.getByText('Dispossessed notes')).toBeVisible();
  await expect(main.getByText('Anarchist utopia')).toBeHidden();
  await expect(main.getByText('Cities on the train')).toBeHidden();
});

const finishedColumn = (page) =>
  page
    .locator('.ck-pipe-col')
    .filter({ has: page.locator('.ck-pipe-name', { hasText: /^Finished$/ }) });

test.describe('layouts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/RDG');
    await expect(page.getByRole('main').getByText('Book club: Kindred')).toBeVisible();
  });

  const openView = (page, name: string) =>
    page.getByRole('banner').getByRole('button', { name, exact: true }).click();

  test('kanban groups cards by status', async ({ page }) => {
    await openView(page, 'Board');
    const column = (label: string) =>
      page
        .locator('.ck-pipe-col')
        .filter({ has: page.locator('.ck-pipe-name', { hasText: new RegExp(`^${label}$`) }) });
    await expect(column('To read')).toContainText('Anarchist utopia');
    await expect(column('Reading')).toContainText('Sower for school');
    await expect(column('Finished')).toContainText('Book club: Kindred');

    const card = page.locator('.ck-deal-card').filter({ hasText: 'Anarchist utopia' });
    await expect(card.getByRole('img', { name: 'priority: High' })).toBeVisible();
  });

  test('kanban drag and drop moves a card to another column', async ({ page, request }) => {
    const name = unique('Drag me');
    const reading = await createObject(request, 'RDG', { name });
    await page.reload();
    await openView(page, 'Board');

    const card = page.locator('.ck-deal-card').filter({ hasText: name });
    const target = finishedColumn(page);
    await expect(card).toBeVisible();

    const from = await card.boundingBox();
    const to = await target.boundingBox();
    const patched = page.waitForResponse(
      (r) => r.request().method() === 'PATCH' && r.url().includes(`/api/v1/RDG/${reading.id}/`)
    );
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    await page.mouse.move(to.x + to.width / 2, to.y + 120, { steps: 20 });
    await page.mouse.up();

    expect((await patched).ok()).toBeTruthy();
    await expect(page.getByText('Status updated')).toBeVisible();
    await page.reload();
    await expect(finishedColumn(page)).toContainText(name);
  });

  test('gallery filters cards by choice', async ({ page }) => {
    await openView(page, 'Covers');
    const main = page.getByRole('main');
    // The eyebrow shows the second field's value (status), not its name.
    await expect(main.getByRole('link', { name: /Anarchist utopia/ }).locator('.ck-gal-cat')).toHaveText('To read');

    await main.getByRole('button', { name: 'Finished', exact: true }).click();
    await expect(main.getByRole('link', { name: /Book club: Kindred/ })).toBeVisible();
    await expect(main.getByRole('link', { name: /Anarchist utopia/ })).toBeHidden();

    await main.getByRole('button', { name: 'All', exact: true }).click();
    await expect(main.getByRole('link', { name: /Anarchist utopia/ })).toBeVisible();
  });

  test('quadrant plots numeric fields and links to the object', async ({ page }) => {
    await openView(page, 'Pages vs rating');
    const main = page.getByRole('main');
    await expect(main.getByText(/items · Pages × Rating/)).toBeVisible();
    for (const quadrant of ['Visionaries', 'Leaders', 'Niche', 'Challengers']) {
      await expect(main.getByText(quadrant, { exact: true })).toBeVisible();
    }
    await page.locator('.ck-qt-row').filter({ hasText: 'Cities on the train' }).click();
    await expect(page).toHaveURL(/\/RDG\d+$/);
    await expect(page.getByRole('banner').getByText('Cities on the train')).toBeVisible();
  });

  test('swimlane splits status columns into priority rows', async ({ page }) => {
    await openView(page, 'Lanes');
    const row = (label: string) => page.locator('.ck-swim-row').filter({ has: page.locator('.ck-srh-label', { hasText: label }) });
    await expect(page.locator('.ck-swim-head')).toContainText('Priority');
    await expect(row('High')).toContainText('Anarchist utopia');
    await expect(row('High')).not.toContainText('Traveller, again');
    await expect(row('Low')).toContainText('Traveller, again');
    // No aggregate_by on this view, so no money totals.
    await expect(page.getByRole('main')).not.toContainText('Grand total');
    await expect(page.getByRole('main')).not.toContainText('DKK');
  });
});
