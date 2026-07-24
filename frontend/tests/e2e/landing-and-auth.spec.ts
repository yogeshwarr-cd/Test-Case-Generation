import { expect, test } from '@playwright/test';

test.describe('Landing and authentication UI', () => {
  test('landing page presents primary content and navigates to login', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 }), 'The landing page heading should be visible.').toBeVisible();
    await expect(page.getByRole('navigation')).toBeVisible();
    const loginLink = page.getByRole('navigation').getByRole('link', { name: 'Log in', exact: true });
    await expect(loginLink).toBeVisible();
    await loginLink.click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  });

  test('theme toggle changes the rendered page theme', async ({ page }) => {
    await page.goto('/');
    const themeToggle = page.getByRole('button', { name: 'Toggle theme' });
    await expect(themeToggle).toBeVisible();
    const initialDarkMode = await page.locator('html').evaluate((element) => element.classList.contains('dark'));
    await themeToggle.click();
    await expect.poll(
      () => page.locator('html').evaluate((element) => element.classList.contains('dark')),
      { message: 'The visible page theme should change after activating the theme toggle.' },
    ).toBe(!initialDarkMode);
  });

  test('login shows client-side validation and accepts completed fields', async ({ page }) => {
    await page.goto('/login');
    const email = page.getByPlaceholder('name@company.com');
    const password = page.locator('input[type="password"]');
    const submit = page.getByRole('button', { name: 'Sign In with Email' });
    await expect(email).toBeVisible();
    await expect(password).toBeVisible();
    await expect(submit).toBeEnabled();
    await submit.click();
    await expect(page.getByText('Please fill in all fields', { exact: true })).toBeVisible();
    await email.fill('ui.tester@example.com');
    await password.fill('valid-ui-value');
    await submit.click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
  });

  test('registration placeholder returns to login', async ({ page }) => {
    await page.goto('/register');
    await expect(page.getByRole('heading', { name: 'Create Account' })).toBeVisible();
    const backLink = page.getByRole('link', { name: 'Back to Login' });
    await expect(backLink).toBeVisible();
    await backLink.click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  });
});
