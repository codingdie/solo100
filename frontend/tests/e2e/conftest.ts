import { test as base, Page } from '@playwright/test';

/** 自定义 test fixture，带默认 timeout。 */
export const test = base.extend<{ testPage: Page }>({
  testPage: async ({ page }, use) => {
    await use(page);
  },
});

export { expect } from '@playwright/test';
