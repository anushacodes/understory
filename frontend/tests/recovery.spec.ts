import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

// Only point this at the worker started for this local test run.
test('reload restores a queued import and reports the stopped worker', async ({
  page,
  request,
}) => {
  const workerPid = Number(process.env.UNDERSTORY_TEST_WORKER_PID);
  test.skip(!workerPid, 'Requires the explicitly selected local project worker PID.');
  test.setTimeout(100000);
  const token =
    readFileSync(new URL('../../.env', import.meta.url), 'utf8').match(
      /^OWNER_TOKEN=(.+)$/m,
    )?.[1] ?? '';
  const headers = { Authorization: `Bearer ${token}` };
  let jobId: string | undefined;
  const command = execFileSync('ps', ['-p', String(workerPid), '-o', 'command='], {
    encoding: 'utf8',
  });
  expect(command.trim()).toMatch(/(?:^|[/ ])understory-worker$/);
  const cwd = execFileSync('lsof', ['-a', '-p', String(workerPid), '-d', 'cwd', '-Fn'], {
    encoding: 'utf8',
  });
  const project = resolve(fileURLToPath(new URL('../../', import.meta.url)));
  expect(cwd.split('\n')).toContain(`n${project}`);
  process.kill(workerPid, 'SIGSTOP');
  try {
    const repos = await request.get('http://127.0.0.1:8017/v1/repositories', { headers });
    const repo = (await repos.json()).items.find(
      (item: { name: string }) => item.name === 'understory/fixture',
    );
    const accepted = await request.post(
      `http://127.0.0.1:8017/v1/repositories/${repo.id}/imports`,
      {
        headers: { ...headers, 'Idempotency-Key': `browser-reload-${Date.now()}` },
        data: { ref: 'b' },
      },
    );
    expect(accepted.status()).toBe(202);
    jobId = (await accepted.json()).job_id;
    await page.goto('/#workspace');
    await page.getByLabel('Owner token', { exact: true }).fill(token);
    await page.getByRole('button', { name: 'Open workspace', exact: true }).click();
    await page.locator('select[aria-label="Repository"]').selectOption(repo.id);
    await expect(page.locator('.job-panel')).toContainText('queued');
    await page.reload();
    await page.getByLabel('Owner token', { exact: true }).fill(token);
    await page.getByRole('button', { name: 'Open workspace', exact: true }).click();
    await expect(page.locator('.job-panel')).toContainText('queued');
    await expect(page.locator('.job-panel')).toContainText('Local worker is offline', {
      timeout: 65000,
    });
    await page.getByRole('button', { name: 'Cancel job', exact: true }).click();
    await expect(page.locator('.job-panel')).toContainText('cancelled');
  } finally {
    if (jobId)
      await request.post(`http://127.0.0.1:8017/v1/jobs/${jobId}/cancel`, { headers, data: {} });
    process.kill(workerPid, 'SIGCONT');
  }
});
