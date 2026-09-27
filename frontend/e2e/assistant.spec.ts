import { expect, test } from '@playwright/test';

test('assistant sidebar follows the screen and keeps its conversation', async ({ page }) => {
  await page.goto('/BOK');
  await expect(page.getByRole('button', { name: 'Toggle assistant' })).toBeVisible();
  await page.keyboard.press('ControlOrMeta+j');
  const sidebar = page.getByRole('complementary', { name: 'Assistant chat' });
  await expect(sidebar.getByText('Ready')).toBeVisible();

  await page.getByRole('checkbox', { name: 'Select BOK1' }).check();
  await expect(sidebar.getByTestId('assistant-screen')).toHaveText('BOK list · 1 selected');

  // e2e runs the demo with pydantic-ai's test model, which answers with canned text.
  await sidebar.getByPlaceholder('Ask Assistant…').fill('Hello there');
  await sidebar.getByPlaceholder('Ask Assistant…').press('Enter');
  await expect(sidebar.getByText('Ready')).toBeVisible();
  await expect(sidebar.locator('.ck-bubble-in')).not.toHaveCount(0);

  await page.getByRole('main').getByRole('link', { name: 'BOK1', exact: true }).click();
  await expect(sidebar.getByTestId('assistant-screen')).toHaveText('BOK1');

  // Open state and the conversation survive a reload.
  await page.reload();
  await expect(sidebar.getByText('Hello there')).toBeVisible();

  await page.keyboard.press('ControlOrMeta+j');
  await expect(sidebar).toBeHidden();
});
