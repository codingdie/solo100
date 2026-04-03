import { expect, test } from './conftest';

test.describe('Projects Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/projects');
  });

  test('should display projects list page', async ({ page }) => {
    await expect(page).toHaveTitle(/solo100/i);
    // 检查页面加载了 projects 相关内容（标题或空状态）
    const heading = page.getByRole('heading', { name: /project/i }).or(page.getByText('No projects'));
    await expect(heading).toBeVisible();
  });

  test('should create a new project', async ({ page }) => {
    // 导航到创建页面
    await page.getByRole('link', { name: /new project/i }).or(page.getByRole('button', { name: /new project/i })).click();

    // 填写表单
    await page.getByLabel(/name/i).fill('e2e-test-project');
    await page.getByLabel(/ssh url/i).fill('file:///tmp/solo100-test-remote.git');
    await page.getByLabel(/default branch/i).fill('main');

    // 提交
    await page.getByRole('button', { name: /create|submit|save/i }).click();

    // 验证项目出现在列表中
    await expect(page.getByText('e2e-test-project')).toBeVisible();
  });
});
