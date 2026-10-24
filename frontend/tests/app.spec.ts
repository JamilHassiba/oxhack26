import { test, expect } from '@playwright/test';
test('create an agent with explicit tool permissions', async ({ page }) => {
  await page.goto('/agents');
  await expect(page.getByRole('heading', { name: 'Your people. Powered by AI.' })).toBeVisible();
  await page.screenshot({ path: `/tmp/concierge-${test.info().project.name}.png`, fullPage: true });
  await page.getByRole('button', { name: 'Create agent', exact: true }).click();
  await page.getByRole('textbox', { name: 'Agent name' }).fill('Robin');
  await page
    .getByRole('textbox', { name: 'Personality' })
    .fill('A practical assistant for my schedule.');
  await page.getByRole('checkbox', { name: 'Payments' }).uncheck();
  await page.getByRole('dialog').getByRole('button', { name: 'Create agent', exact: true }).click();
  const card = page
    .getByRole('article')
    .filter({ has: page.getByRole('heading', { name: 'Robin', exact: true }) });
  await expect(card).toBeVisible();
  await expect(card.getByText('Payments', { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Robin', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});
test('booking, approval, persisted transcript, calendar export, analytics', async ({ page }) => {
  await page.goto('/chat/maya');
  await page.getByRole('button', { name: 'Make dinner plans' }).click();
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Thinking it through', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve £20.00' })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByText('Restaurant', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Approve £20.00' }).click();
  await expect(page.getByText('All taken care of.', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText('All taken care of.', { exact: true })).toBeVisible();
  await page.getByRole('navigation').getByRole('link', { name: 'Calendar' }).click();
  await expect(
    page.getByRole('heading', { name: 'Dinner at The Ivy Oxford · 4 guests' }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export calendar' }).click();
  expect((await downloadPromise).suggestedFilename()).toBe('concierge.ics');
  await page.getByRole('button', { name: 'Month', exact: true }).click();
  await expect(
    page.getByText('Dinner at The Ivy Oxford · 4 guests', { exact: true }),
  ).toBeVisible();
  await page.getByRole('navigation').getByRole('link', { name: 'Analytics' }).click();
  await expect(page.getByText('100%', { exact: true }).first()).toBeVisible();
});
test('decline and no-answer failure remain actionable', async ({ page }) => {
  await page.goto('/chat/maya');
  await page.getByRole('button', { name: 'Make dinner plans' }).click();
  await page.getByRole('button', { name: 'Send message' }).click();
  await page.getByRole('button', { name: 'Decline', exact: true }).click({ timeout: 15000 });
  await expect(page.getByText('Your decision, respected.')).toBeVisible();
  await page.getByRole('textbox', { name: 'Message Maya' }).fill('no answer');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Let’s try another way')).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('textbox', { name: 'Message Maya' })).toBeEnabled();
  await page.getByRole('navigation').getByRole('link', { name: 'Calendar' }).click();
  await expect(page.getByText('Your next plan is a conversation away')).toBeVisible();
});
