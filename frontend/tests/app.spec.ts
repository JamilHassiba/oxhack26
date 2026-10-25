import { test, expect } from '@playwright/test';
import { scenarios } from '../src/features/demo/scenarios';
// No shortcut boxes, sidebar or scenario picker: tests type requests (a scenario's prompt plays that
// demo scenario) and visit pages directly.
const BOOKING =
  'Book a table for 4 at The Ivy Oxford tomorrow at 6pm. They may ask for a £20 deposit.';
test('create an agent with explicit tool permissions', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Your agents' })).toBeVisible();
  await page.screenshot({ path: `/tmp/concierge-${test.info().project.name}.png`, fullPage: true });
  await page.getByRole('button', { name: 'Create agent', exact: true }).click();
  await page.getByRole('textbox', { name: 'Agent name' }).fill('Robin');
  await page.getByRole('dialog').getByRole('checkbox', { name: 'Payments' }).uncheck();
  await page.getByRole('dialog').getByRole('button', { name: 'Create agent', exact: true }).click();
  // A new agent opens straight into its chat.
  await expect(page.getByRole('textbox', { name: 'Message Robin' })).toBeVisible();
  await page.goto('/');
  const card = page
    .getByRole('article')
    .filter({ has: page.getByRole('heading', { name: 'Robin', exact: true }) });
  await expect(card).toBeVisible();
  await expect(card.getByRole('checkbox', { name: 'Payments', exact: true })).not.toBeChecked();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Robin', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});
test('booking, approval, persisted transcript, call result, analytics', async ({ page }) => {
  await page.goto('/chat/maya');
  await page.getByRole('textbox', { name: 'Message Maya' }).fill(BOOKING);
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
  await expect(page.getByRole('table', { name: 'Call result' })).toContainText('Confirmed');
  await page.goto('/analytics');
  await expect(page.getByText('100%', { exact: true }).first()).toBeVisible();
});
test('decline and no-answer failure remain actionable', async ({ page }) => {
  await page.goto('/chat/maya');
  await page.getByRole('textbox', { name: 'Message Maya' }).fill(BOOKING);
  await page.getByRole('button', { name: 'Send message' }).click();
  await page.getByRole('button', { name: 'Decline', exact: true }).click({ timeout: 15000 });
  await expect(page.getByText('Your decision, respected.')).toBeVisible();
  await page.getByRole('textbox', { name: 'Message Maya' }).fill('no answer');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Let’s try another way')).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('textbox', { name: 'Message Maya' })).toBeEnabled();
});

test('agent arrows preserve separate permission choices, then save on entry', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Maya', exact: true })).toBeVisible();
  await page.getByRole('checkbox', { name: 'Phone calls', exact: true }).uncheck();
  await page.getByRole('button', { name: 'Next agent' }).click();
  await expect(page.getByRole('heading', { name: 'Leo', exact: true })).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Phone calls', exact: true })).not.toBeChecked();
  await page.getByRole('button', { name: 'Previous agent' }).click();
  await expect(page.getByRole('checkbox', { name: 'Phone calls', exact: true })).not.toBeChecked();
  await page.getByRole('button', { name: 'Enter agent', exact: true }).click();
  await expect(page).toHaveURL(/\/chat\/maya$/);
  await expect(page.getByRole('heading', { name: 'What can I help with?' })).toBeVisible();
  await page.getByRole('link', { name: 'concierge. Home' }).click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Maya', exact: true })).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Phone calls', exact: true })).not.toBeChecked();
  await page.getByRole('button', { name: 'Next agent' }).click();
  await page.getByRole('button', { name: 'Next agent' }).click();
  await expect(page.getByRole('heading', { name: 'Maya', exact: true })).toBeVisible();
  await page.screenshot({
    path: `/tmp/concierge-picker-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test('payments remain accessible outside the call transcript', async ({ page }) => {
  await page.goto('/chat/maya');
  await page.getByRole('textbox', { name: 'Message Maya' }).fill(BOOKING);
  await page.getByRole('button', { name: 'Send message' }).click();
  await page.goto('/payments');
  await expect(page.getByRole('button', { name: 'Approve £20.00' })).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole('button', { name: 'Approve £20.00' }).click();
  await expect(page.getByText('Payment approved', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'View conversation' }).click();
  await expect(page.getByText('All taken care of.', { exact: true })).toBeVisible();
  const details = page.locator('.call-details');
  await expect(details).not.toHaveAttribute('open', '');
  await details.locator('summary').click();
  await expect(page.getByText('Restaurant', { exact: true })).toBeVisible();
});

test('important text has readable contrast and controls fit the viewport', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Maya', exact: true })).toBeVisible();
  const ratios = await page
    .locator(
      'h1, .selected-agent h2, .permission-row > span, .agent-role, .enter-agent, .agent-position',
    )
    .evaluateAll((elements) => {
      const rgb = (value: string) => (value.match(/[\d.]+/g) || []).map(Number);
      const luminance = (color: number[]) =>
        color
          .slice(0, 3)
          .map((v) => {
            const n = v / 255;
            return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
          })
          .reduce((total, v, i) => total + v * [0.2126, 0.7152, 0.0722][i], 0);
      return elements.map((element) => {
        let parent: Element | null = element;
        let background = [255, 255, 255];
        while (parent) {
          const color = rgb(getComputedStyle(parent).backgroundColor);
          if (color.length === 3 || color[3] === 1) {
            background = color;
            break;
          }
          parent = parent.parentElement;
        }
        const foreground = rgb(getComputedStyle(element).color);
        const light = luminance(foreground),
          dark = luminance(background);
        return {
          text: element.textContent,
          ratio: (Math.max(light, dark) + 0.05) / (Math.min(light, dark) + 0.05),
        };
      });
    });
  for (const item of ratios)
    expect(item.ratio, `Contrast for ${item.text}`).toBeGreaterThanOrEqual(4.5);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('edit and delete an agent', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Manage agent').click();
  await page.getByRole('button', { name: 'Edit agent', exact: true }).click();
  await page.getByRole('textbox', { name: 'Agent name' }).fill('Maya edited');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByRole('heading', { name: 'Maya edited', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Duplicate agent' })).toHaveCount(0);
  await page.getByLabel('Manage agent').click();
  await page.getByRole('button', { name: 'Delete agent', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete agent', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Maya edited', exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Leo', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Leo', exact: true })).toBeVisible();
});
test('history searches transcripts, filters tasks, and opens a direct task view', async ({
  page,
}) => {
  await page.goto('/chat/maya');
  await page.getByRole('textbox', { name: 'Message Maya' }).fill(scenarios.alternative_time.prompt);
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('All taken care of.', { exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.goto('/history');
  await page.getByRole('textbox', { name: 'Search history' }).fill('No deposit is needed');
  await expect(page.locator('.history-row')).toHaveCount(1);
  await page.getByLabel('Filter by status').selectOption('failed');
  await expect(page.getByText('No matching tasks', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await page.locator('.history-row').click();
  await expect(page.getByText('All taken care of.', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText('19:00', { exact: false }).first()).toBeVisible();
  await page.getByText('Call transcript', { exact: true }).click();
  await expect(page.getByText('Restaurant', { exact: true })).toBeVisible();
  await page.screenshot({
    path: `/tmp/concierge-history-${test.info().project.name}.png`,
    fullPage: true,
  });
});
test('fully booked and no-answer scenarios fail cleanly and unlock the composer', async ({
  page,
}) => {
  await page.goto('/chat/maya');
  await page.getByRole('textbox', { name: 'Message Maya' }).fill(scenarios.fully_booked.prompt);
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(
    page.getByText('The restaurant is fully booked. No reservation or payment was made.'),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('button', { name: 'Approve £20.00' })).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Message Maya' }).fill(scenarios.no_answer.prompt);
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(
    page.getByText('The restaurant did not answer. Try again or choose another restaurant.'),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('textbox', { name: 'Message Maya' })).toBeEnabled();
});
test('active tasks block deletion until the deposit is declined', async ({ page }) => {
  await page.goto('/chat/maya');
  await page.getByRole('textbox', { name: 'Message Maya' }).fill(scenarios.declined_deposit.prompt);
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByRole('button', { name: 'Decline', exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole('link', { name: 'concierge. Home' }).click();
  await page.getByLabel('Manage agent').click();
  await page.getByRole('button', { name: 'Delete agent', exact: true }).click();
  await expect(
    page.getByRole('dialog').getByRole('button', { name: 'Delete agent', exact: true }),
  ).toBeDisabled();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.goto('/chat');
  await page.getByRole('button', { name: 'Decline', exact: true }).click();
  await expect(page.getByText('Your decision, respected.')).toBeVisible();
  await page.getByRole('link', { name: 'concierge. Home' }).click();
  await page.getByLabel('Manage agent').click();
  await page.getByRole('button', { name: 'Delete agent', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete agent', exact: true }).click();
  await page.goto('/history');
  await page.locator('.history-row').click();
  await expect(page.getByText('Your decision, respected.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open chat' })).toHaveCount(0);
});
