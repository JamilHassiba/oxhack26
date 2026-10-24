import { test, expect } from '@playwright/test';
test('create an agent with explicit tool permissions', async ({ page }) => {
  await page.goto('/agents');
  await expect(page.getByRole('heading', { name: 'Choose your agent' })).toBeVisible();
  await page.screenshot({ path: `/tmp/concierge-${test.info().project.name}.png`, fullPage: true });
  await page.getByRole('button', { name: 'Create agent', exact: true }).click();
  await page.getByRole('textbox', { name: 'Agent name' }).fill('Robin');
  await page
    .getByRole('textbox', { name: 'Personality' })
    .fill('A practical assistant for my schedule.');
  await page.getByRole('dialog').getByRole('checkbox', { name: 'Payments' }).uncheck();
  await page.getByRole('dialog').getByRole('button', { name: 'Create agent', exact: true }).click();
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
test('booking, approval, persisted transcript, calendar export, analytics', async ({ page }) => {
  await page.goto('/chat/maya');
  await page.getByRole('button', { name: 'Book a table' }).click();
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
  await page.getByRole('link', { name: 'Analytics' }).click();
  await expect(page.getByText('100%', { exact: true }).first()).toBeVisible();
});
test('decline and no-answer failure remain actionable', async ({ page }) => {
  await page.goto('/chat/maya');
  await page.getByRole('button', { name: 'Book a table' }).click();
  await page.getByRole('button', { name: 'Send message' }).click();
  await page.getByRole('button', { name: 'Decline', exact: true }).click({ timeout: 15000 });
  await expect(page.getByText('Your decision, respected.')).toBeVisible();
  await page.getByRole('textbox', { name: 'Message Maya' }).fill('no answer');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Let’s try another way')).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('textbox', { name: 'Message Maya' })).toBeEnabled();
  await page.getByRole('navigation').getByRole('link', { name: 'Calendar' }).click();
  await expect(page.getByText('No plans yet')).toBeVisible();
});

test('agent arrows preserve separate permission choices, then save on entry', async ({ page }) => {
  await page.goto('/agents');
  await expect(page.getByRole('heading', { name: 'Maya', exact: true })).toBeVisible();
  await page.getByRole('checkbox', { name: 'Phone calls', exact: true }).uncheck();
  await page.getByRole('button', { name: 'Next agent' }).click();
  await expect(page.getByRole('heading', { name: 'Leo', exact: true })).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Phone calls', exact: true })).not.toBeChecked();
  await page.getByRole('button', { name: 'Previous agent' }).click();
  await expect(page.getByRole('checkbox', { name: 'Phone calls', exact: true })).not.toBeChecked();
  await page.getByRole('button', { name: 'Enter agent', exact: true }).click();
  await expect(page).toHaveURL(/\/chat\/maya$/);
  await expect(page.getByRole('button', { name: 'Book a table' })).toHaveCount(0);
  await page
    .getByRole('navigation')
    .getByRole('link', { name: /Agents/ })
    .click();
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
  await page.getByRole('button', { name: 'Book a table' }).click();
  await page.getByRole('button', { name: 'Send message' }).click();
  await page.getByRole('navigation').getByRole('link', { name: 'Payments', exact: true }).click();
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
  await page.goto('/agents');
  await expect(page.getByRole('heading', { name: 'Maya', exact: true })).toBeVisible();
  const ratios = await page
    .locator(
      'h1, .selected-agent h2, .permission-row > span, .agent-role, .enter-agent, .permissions-note, .agent-position',
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
