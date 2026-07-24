import { expect, test } from '@playwright/test';

test.describe('Dashboard UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.removeItem('ba-workspaces'));
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Projects', exact: true }), 'The dashboard UI did not load.').toBeVisible();
  });

  test('empty state leads to the new project form', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'No projects yet' })).toBeVisible();
    const createProject = page.getByRole('link', { name: 'Create New Project' });
    await expect(createProject).toBeVisible();
    await createProject.click();
    await expect(page.getByRole('heading', { name: 'Create New Project' })).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/\/projects\/new$/);
    await expect(page.getByPlaceholder('e.g. E-Commerce Checkout Redesign')).toBeVisible();
  });

  test('profile menu opens, closes, and logout navigates home', async ({ page }) => {
    const profile = page.getByRole('button', { name: 'User Profile' });
    await profile.click();
    const profileMenu = page.locator('header div.absolute.right-0');
    const logout = profileMenu.getByRole('button', { name: 'Logout' });
    await expect(logout).toBeVisible();
    await expect(page.getByText('Jane Smith', { exact: true })).toBeVisible();
    await profile.click();
    await expect(logout).toBeHidden();
    await profile.click();
    await logout.click();
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('navigation')).toBeVisible();
  });

  test('search control is visible and accepts user input', async ({ page }) => {
    const search = page.getByPlaceholder('Search stories, summaries, or IDs...');
    await expect(search).toBeVisible();
    await expect(search).toBeEnabled();
    await search.fill('checkout');
    await expect(search).toHaveValue('checkout');
  });
});
