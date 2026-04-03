import { expect, test } from './conftest';

/** 创建测试用项目并返回其 URL */
async function createTestProject(page: import('@playwright/test').Page, name = 'e2e-workflow-project') {
  await page.goto('/projects');
  await page.getByRole('button', { name: /new project/i }).click();
  await page.getByLabel(/name/i).fill(name);
  await page.getByLabel(/ssh url/i).fill('file:///tmp/solo100-test-remote.git');
  await page.getByLabel(/default branch/i).fill('main');
  await page.getByRole('button', { name: /create|submit|save/i }).click();
  await expect(page.getByText(name)).toBeVisible();
}

test.describe('Feature Workflow', () => {
  test('should create and start a feature', async ({ page }) => {
    await createTestProject(page);

    // 创建 Feature
    await page.getByRole('button', { name: /new feature/i }).click();
    await page.getByLabel(/title/i).fill('e2e-test-feature');
    await page.getByLabel(/description/i).fill('Playwright E2E 测试 Feature');
    await page.getByRole('button', { name: /create|submit|save/i }).click();
    await expect(page.getByText('e2e-test-feature')).toBeVisible();

    // 启动开发流程
    const featureCard = page.getByText('e2e-test-feature').locator('..');
    await featureCard.getByRole('button', { name: /start/i }).click();

    // 验证状态变为 brainstorming
    await expect(page.getByText(/brainstorming/i)).toBeVisible({ timeout: 5000 });
  });

  test('should show feature detail with status badge', async ({ page }) => {
    await createTestProject(page);
    await page.getByRole('button', { name: /new feature/i }).click();
    await page.getByLabel(/title/i).fill('detail-test-feature');
    await page.getByLabel(/description/i).fill('测试详情页');
    await page.getByRole('button', { name: /create|submit|save/i }).click();

    // 点击查看详情
    await page.getByText('detail-test-feature').click();
    await expect(page.getByText('pending')).toBeVisible();
    await expect(page.getByText('detail-test-feature')).toBeVisible();
  });
});
