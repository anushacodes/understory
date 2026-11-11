import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

const ownerToken =
  process.env.UNDERSTORY_TEST_TOKEN ??
  readFileSync(new URL('../../.env', import.meta.url), 'utf8').match(/^OWNER_TOKEN=(.+)$/m)?.[1];

async function connect(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Open Understory', exact: true }).click();
  await page.getByLabel('Owner token', { exact: true }).fill(ownerToken ?? '');
  await page.getByRole('button', { name: 'Open workspace', exact: true }).click();
  await expect(page.locator('select[aria-label="Repository"]')).toHaveValue(/.+/);
}

async function mobileTab(page: Page, tab: string) {
  if (await page.locator('.mobile-tabs').isVisible())
    await page.locator('.mobile-tabs').getByRole('button', { name: tab, exact: true }).click();
}

test('landing follows the supplied wordmark and theme direction', async ({ page }, info) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Understand the codebeneath the surface.',
  );
  await expect(page.locator('.wordmark em')).toHaveText('under');
  await expect(page.locator('body')).not.toContainText('open issue');
  const fonts = await page
    .locator('h1')
    .evaluate((element) => getComputedStyle(element).fontFamily);
  expect(fonts).toContain('Instrument Serif');
  await page.screenshot({ path: info.outputPath('landing-light.png'), fullPage: true });
  await page.getByRole('button', { name: 'Use dark theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.screenshot({ path: info.outputPath('landing-dark.png'), fullPage: true });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
});

test('browse real indexed source and retain pane access', async ({ page }, info) => {
  await connect(page);
  await mobileTab(page, 'Files');
  await expect(page.getByText('Synthetic example repository', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'validation.py', exact: true }).click();
  await expect(page.getByRole('region', { name: 'app/validation.py source code' })).toBeVisible();
  await expect(page.locator('.code-lines')).toContainText('validate_payload');
  await expect(page.locator('.code-lines')).toContainText('ValidationError');
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.screenshot({ path: info.outputPath('workspace-source.png'), fullPage: true });
  await page.getByRole('button', { name: 'Expand source', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Restore workspace panes' })).toBeVisible();
  await page.getByRole('button', { name: 'Restore workspace panes' }).click();
  await mobileTab(page, 'Workspace');
  await expect(page.locator('.question-toolbar strong')).toHaveText('Repository overview');
});

test('search real evidence and open exact source ranges', async ({ page }, info) => {
  await connect(page);
  await mobileTab(page, 'Files');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByLabel('Find the code you’re looking for.')).toBeVisible();
  await page.getByLabel('Find the code you’re looking for.').fill('validate_payload');
  await page.getByLabel('Search mode').selectOption('exact');
  await page.getByRole('button', { name: 'Run search' }).click();
  await expect(page.locator('.search-result').first()).toBeVisible();
  await page.locator('.search-result').filter({ hasText: 'app/validation.py' }).first().click();
  await expect(page.locator('.cited-line').first()).toBeVisible();
  await expect(page.locator('.selection-label')).toContainText('selected');
  await page.screenshot({ path: info.outputPath('workspace-search.png'), fullPage: true });
});

test('reduced motion and keyboard focus remain usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  expect(
    await page.locator('.meadow').evaluate((element) => getComputedStyle(element).animationName),
  ).toBe('none');
  await page.keyboard.press('Tab');
  const focused = await page
    .locator(':focus')
    .evaluate((element) => getComputedStyle(element).outlineStyle);
  expect(focused).not.toBe('none');
  await expect(page.getByRole('button', { name: 'Open Understory', exact: true })).toBeVisible();
});
