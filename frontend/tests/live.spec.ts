import { test, expect } from '@playwright/test';
import type { Task } from '../src/types';
const agent = {
  id: 'backend-maya',
  name: 'Maya',
  persona: 'Helpful',
  voice: 'Warm',
  tools: ['phone', 'payments', 'calendar'],
};
test('HTTP adapter, named SSE frames, approval, and reconnect fallback', async ({ page }) => {
  let approved = false;
  let receivedMessage = '';
  const task: Task = {
    id: 'backend-task',
    agent_id: agent.id,
    goal: 'Book dinner',
    status: 'awaiting_approval',
    created_at: new Date().toISOString(),
    events: [],
    call: {
      id: 'backend-call',
      status: 'answered',
      started_at: new Date().toISOString(),
      transcript: [],
    },
    payment: {
      id: 'backend-payment',
      task_id: 'backend-task',
      amount: 2000,
      currency: 'GBP',
      status: 'pending_approval',
    },
  };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/agents') return route.fulfill({ json: [agent] });
    if (path.endsWith('/chat')) {
      receivedMessage = route.request().postDataJSON().message;
      return route.fulfill({ json: { task_id: task.id } });
    }
    if (path.endsWith('/approve')) {
      approved = true;
      return route.fulfill({ status: 204 });
    }
    if (path.endsWith('/events/stream')) {
      const event = {
        ts: '2026-10-24T12:00:00Z',
        call_id: task.call!.id,
        kind: 'transcript_line',
        payload: { speaker: 'Restaurant', text: 'Live backend transcript received.' },
      };
      return route.fulfill({
        contentType: 'text/event-stream',
        body: `id: 1\nevent: transcript_line\ndata: ${JSON.stringify(event)}\n\n`,
      });
    }
    if (path === `/api/tasks/${task.id}`)
      return route.fulfill({
        json: approved
          ? {
              ...task,
              status: 'done',
              summary: 'Reservation confirmed by backend.',
              call: {
                ...task.call,
                ended_at: new Date().toISOString(),
                transcript: [{ speaker: 'Restaurant', text: 'Live backend transcript received.' }],
              },
              payment: { ...task.payment, status: 'paid' },
            }
          : task,
      });
    return route.fulfill({ status: 404, json: { detail: 'Unknown endpoint' } });
  });
  await page.goto(`/chat/${agent.id}`);
  await expect(page.getByText('Connected to backend')).toBeVisible();
  await page.getByRole('textbox', { name: 'Message Maya' }).fill('Book dinner');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Live backend transcript received.')).toBeVisible();
  expect(receivedMessage).toBe('Book dinner');
  await page.getByRole('button', { name: 'Approve £20.00' }).click();
  await expect(page.getByText('Reservation confirmed by backend.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Reservation confirmed by backend.')).toBeVisible();
});
test('failed sends preserve the draft and can be retried', async ({ page }) => {
  let fail = true;
  await page.route('**/api/agents', (route) => route.fulfill({ json: [agent] }));
  await page.route('**/api/agents/*/chat', (route) =>
    route.fulfill(
      fail
        ? { status: 503, json: { detail: 'Agent is temporarily unavailable.' } }
        : { json: { task_id: 'retried' } },
    ),
  );
  await page.route('**/api/tasks/retried', (route) =>
    route.fulfill({
      json: {
        id: 'retried',
        agent_id: agent.id,
        goal: 'Please book dinner',
        status: 'done',
        summary: 'Retry succeeded.',
        created_at: new Date().toISOString(),
        events: [],
      },
    }),
  );
  await page.goto(`/chat/${agent.id}`);
  const composer = page.getByRole('textbox', { name: 'Message Maya' });
  await composer.fill('Please book dinner');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByRole('alert')).toContainText('Agent is temporarily unavailable.');
  await expect(composer).toHaveValue('Please book dinner');
  fail = false;
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Retry succeeded.')).toBeVisible();
});

test('enter agent persists selected tools to the API and handles a save error', async ({
  page,
}) => {
  let fail = true;
  let current = { ...agent, tools: [...agent.tools] };
  let receivedTools: string[] = [];
  await page.route('**/api/agents', (route) => route.fulfill({ json: [current] }));
  await page.route(`**/api/agents/${agent.id}`, (route) => {
    receivedTools = route.request().postDataJSON().tools;
    if (fail)
      return route.fulfill({ status: 503, json: { detail: 'Could not save permissions.' } });
    current = { ...current, tools: receivedTools };
    return route.fulfill({ json: current });
  });
  await page.goto('/agents');
  await page.getByRole('checkbox', { name: 'Phone calls', exact: true }).uncheck();
  await page.getByRole('button', { name: 'Enter agent', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Could not save permissions.');
  await expect(page).toHaveURL(/\/agents$/);
  await expect(page.getByRole('checkbox', { name: 'Phone calls', exact: true })).not.toBeChecked();
  fail = false;
  await page.getByRole('button', { name: 'Enter agent', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/chat/${agent.id}$`));
  expect(receivedTools).toEqual(['payments', 'calendar']);
  await expect(page.getByRole('button', { name: 'Book a table' })).toHaveCount(0);
});
