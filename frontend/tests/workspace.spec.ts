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
  await mobileTab(page, 'Files');
  await page
    .locator('select[aria-label="Repository"]')
    .selectOption({ label: 'understory/fixture' });
  await mobileTab(page, 'Workspace');
}

async function mobileTab(page: Page, tab: string) {
  await expect(page.locator('.mobile-tabs')).toBeAttached();
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

test('ask with groq, reopen history and export pinned evidence', async ({ page }, info) => {
  test.skip(process.env.UNDERSTORY_LIVE_TESTS !== '1', 'Real Groq calls require explicit opt-in.');
  test.setTimeout(120000);
  await connect(page);
  await mobileTab(page, 'Files');
  await page.getByRole('button', { name: 'New question', exact: true }).click();
  await mobileTab(page, 'Workspace');
  const question = 'How are boolean amounts rejected?';
  // Recheck the complete UI with a prior successful run without spending quota again.
  if (process.env.UNDERSTORY_REPLAY_KEY) {
    await page.route('**/v1/repositories/*/questions', (route) =>
      route.continue({
        headers: {
          ...route.request().headers(),
          'idempotency-key': process.env.UNDERSTORY_REPLAY_KEY!,
        },
      }),
    );
  }
  await page.getByLabel('Ask about this repository', { exact: true }).fill(question);
  await page.getByRole('button', { name: 'Ask question', exact: true }).click();
  await expect(page.locator('.answer-paragraph').first()).toBeVisible({ timeout: 90000 });
  await expect(page.locator('.answer-content')).toContainText(/bool|boolean/i);
  await page.locator('.citation-number').first().click();
  await expect(page.locator('.cited-line').first()).toBeVisible();
  await mobileTab(page, 'Workspace');
  const downloading = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export answer', exact: true }).click();
  const download = await downloading;
  const file = await download.path();
  const exported = JSON.parse(readFileSync(file!, 'utf8'));
  expect(exported.output.snapshot_id).toBe(exported.snapshot_id);
  expect(exported.output.citations.length).toBeGreaterThan(0);
  expect(exported.usage[0].provider).toBe('groq');
  await page.screenshot({ path: info.outputPath('workspace-answer.png'), fullPage: true });
  await mobileTab(page, 'Files');
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await mobileTab(page, 'Workspace');
  await page.locator('.history-list button').filter({ hasText: question }).first().click();
  await expect(page.locator('.answer-paragraph').first()).toBeVisible();
  await page.reload();
  await page.getByLabel('Owner token', { exact: true }).fill(ownerToken ?? '');
  await page.getByRole('button', { name: 'Open workspace', exact: true }).click();
  await mobileTab(page, 'Files');
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await mobileTab(page, 'Workspace');
  await page.locator('.history-list button').filter({ hasText: question }).first().click();
  await expect(page.locator('.answer-paragraph').first()).toBeVisible();
});

test('saved overview and insufficient evidence remain readable', async ({ page }) => {
  test.skip(process.env.UNDERSTORY_LIVE_TESTS !== '1', 'Requires the live release fixture.');
  await connect(page);
  await mobileTab(page, 'Files');
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await mobileTab(page, 'Workspace');
  await page
    .locator('.history-list button')
    .filter({ hasText: 'production encryption key value' })
    .first()
    .click();
  await expect(page.locator('.answer-baseline')).toContainText('insufficient evidence');
  await expect(page.locator('.evidence-gaps')).toBeVisible();
  await mobileTab(page, 'Files');
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await mobileTab(page, 'Workspace');
  await page
    .locator('.history-list button')
    .filter({ hasText: 'Repository overview' })
    .first()
    .click();
  await expect(
    page.getByRole('heading', { name: 'How this repository fits together' }),
  ).toBeVisible();
  await expect(page.locator('.citation-number').first()).toBeVisible();
});

test('untrusted source markup is rendered as text', async ({ page }) => {
  await connect(page);
  await page.route('**/v1/repositories/*/files?*', async (route) => {
    const response = await route.fetch();
    const source = await response.json();
    await route.fulfill({
      json: {
        ...source,
        content:
          '<script>window.__sourceExecuted=true</script>\n<img src=x onerror="window.__sourceExecuted=true">',
        line_count: 2,
        start_line: 1,
        end_line: 2,
        next_start_line: null,
      },
    });
  });
  await mobileTab(page, 'Files');
  await page.getByRole('button', { name: 'validation.py', exact: true }).click();
  await expect(page.locator('.code-lines')).toContainText('<script>');
  expect(
    await page.evaluate(() => (window as unknown as Record<string, unknown>).__sourceExecuted),
  ).toBeUndefined();
  await expect(page.locator('.code-lines script, .code-lines img')).toHaveCount(0);
});
