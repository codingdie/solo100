import { expect, test } from './conftest';

test.describe('Projects Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display projects list page', async ({ page }) => {
    await expect(page).toHaveTitle(/solo100/i);
    await expect(page.getByText('solo100 项目').first()).toBeAttached();
  });

  test('should create a new project', async ({ page }) => {
    await page.getByRole('button', { name: '新建项目' }).click();
    await page.getByPlaceholder('项目名称').fill('e2e-test-project');
    await page.getByPlaceholder('Git SSH 地址').fill('file:///tmp/solo100-test-remote.git');
    await page.getByRole('button', { name: '创建' }).click();
    await expect(page.getByText('e2e-test-project').first()).toBeAttached();
  });
});
