import { expect, test } from '@playwright/test';
import { unique } from './helpers';

test('creates nested related records inline without leaving the form', async ({ page }) => {
  const readingName = unique('E2E reading');
  const bookTitle = unique('E2E book');
  const authorName = unique('E2E author');

  await page.goto('/RDG/create');
  await page.locator('input[name="name"]').fill(readingName);

  // Reading → new Book
  await page.getByRole('main').getByRole('combobox').first().fill(bookTitle);
  await page.getByRole('option', { name: `+ Create book "${bookTitle}"` }).click();
  const bookDialog = page.getByRole('dialog');
  const titleInput = bookDialog.locator('input[name="title"]');
  await expect(titleInput).toHaveValue(bookTitle);
  // Edits made before a nested create must survive it.
  await titleInput.fill(`${bookTitle} v2`);

  // Book → new Author; Esc closes only the top modal.
  await bookDialog.getByRole('combobox').fill(authorName);
  await page.getByRole('option', { name: `+ Create author "${authorName}"` }).click();
  await expect(page.getByRole('dialog')).toHaveCount(2);
  await page.getByRole('dialog').last().locator('input[name="name"]').press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(1);

  // Enter submits only the innermost form.
  await bookDialog.getByRole('combobox').fill(authorName);
  await page.getByRole('option', { name: `+ Create author "${authorName}"` }).click();
  const authorInput = page.getByRole('dialog').last().locator('input[name="name"]');
  await expect(authorInput).toHaveValue(authorName);
  await authorInput.press('Enter');
  await expect(page.getByRole('dialog')).toHaveCount(1);
  await expect(bookDialog.getByText(authorName)).toBeVisible();
  await expect(page).toHaveURL('/RDG/create');

  await bookDialog.getByRole('button', { name: 'Create' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('main').getByText(`${bookTitle} v2`)).toBeVisible();
  await expect(page.locator('input[name="name"]')).toHaveValue(readingName);

  await page.getByRole('main').getByRole('button', { name: 'Create' }).click();
  await expect(page).toHaveURL(/\/RDG\d+$/);
  await expect(page.getByRole('main').getByRole('link', { name: `${bookTitle} v2` })).toBeVisible();
});
