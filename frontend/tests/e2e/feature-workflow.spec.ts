import { expect, test } from './conftest';

async function createProject(page: import('@playwright/test').Page, name: string) {
  const resp = await page.request.post('http://localhost:8000/api/v1/projects', {
    data: { name, ssh_url: 'file:///tmp/solo100-test-remote.git', ssh_key_env: 'KEY' },
  });
  return (await resp.json()).id;
}

test.describe('Feature Workflow', () => {
  test('should create a feature', async ({ page }) => {
    const projectId = await createProject(page, 'e2e-workflow-project');
    await page.goto(`/projects/${projectId}`);
    await expect(page.getByRole('button', { name: '新建 Feature' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: '新建 Feature' }).click();
    await page.getByPlaceholder('Feature 标题').fill('e2e-test-feature');
    await page.getByRole('button', { name: '创建' }).click();
    await expect(page.getByText('e2e-test-feature').first()).toBeAttached({ timeout: 5000 });
  });

  test('should show feature detail with status badge', async ({ page }) => {
    const projectId = await createProject(page, 'e2e-detail-project');
    await page.goto(`/projects/${projectId}`);
    await expect(page.getByRole('button', { name: '新建 Feature' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: '新建 Feature' }).click();
    await page.getByPlaceholder('Feature 标题').fill('detail-test-feature');
    await page.getByRole('button', { name: '创建' }).click();
    const featureLink = page.locator('a').filter({ hasText: 'detail-test-feature' });
    await expect(featureLink).toBeAttached({ timeout: 5000 });
    await featureLink.click();
    await expect(page.getByText('pending').first()).toBeAttached({ timeout: 10000 });
  });
});
