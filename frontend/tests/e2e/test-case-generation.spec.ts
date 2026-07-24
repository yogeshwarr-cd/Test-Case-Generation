import { expect, test } from '@playwright/test';

test.describe('Test-case generation input UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/test-case-generation');
    await expect(
      page.getByRole('heading', { name: 'Generate test scenarios and test cases' }),
      'The test-case generation input UI did not load.',
    ).toBeVisible();
  });

  test('requires a user story before generation', async ({ page }) => {
    await page.getByRole('button', { name: 'Generate test cases' }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'Enter at least one user story' })).toBeVisible();
    await expect(page).toHaveURL(/\/test-case-generation$/);
  });

  test('generation mode switch exposes its selected state', async ({ page }) => {
    const mode = page.getByRole('switch');
    await expect(mode).toHaveAttribute('aria-checked', 'false');
    await expect(mode).toHaveText('Mock OFF');
    await mode.click();
    await expect(mode).toHaveAttribute('aria-checked', 'true');
    await expect(mode).toHaveText('Mock ON');
  });

  test('dynamic user-story controls add and remove visible inputs', async ({ page }) => {
    const userStories = page.locator('fieldset').first();
    const firstStory = page.getByRole('textbox', { name: 'User Stories 1' });
    await firstStory.fill('As a shopper, I want to review my cart.');
    await expect(firstStory).toHaveValue('As a shopper, I want to review my cart.');
    await userStories.getByRole('button', { name: 'Add another' }).click();
    await expect(page.getByRole('textbox', { name: 'User Stories 2' })).toBeVisible();
    await userStories.getByRole('button', { name: 'Remove User Stories item 2' }).click();
    await expect(page.getByRole('textbox', { name: 'User Stories 2' })).toHaveCount(0);
    await expect(firstStory).toHaveValue('As a shopper, I want to review my cart.');
  });

  test('invalid image type displays a visible validation message', async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles({
      name: 'not-an-image.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('frontend-only fixture'),
    });
    await expect(page.getByRole('alert').filter({ hasText: 'Select a PNG, JPEG, or WebP image.' })).toBeVisible();
    await expect(page.getByRole('img', { name: 'Uploaded wireframe or application screenshot preview' })).toHaveCount(0);
  });
});
