import { test, expect, type Page } from '@playwright/test';
import type { Agent, Task } from '../src/types';
const agent: Agent = {
  id: 'backend-maya',
  name: 'Maya',
  voice: 'Warm',
  tools: ['phone', 'payments', 'calendar'],
};
const finished = (id = 'previous'): Task => ({
  id,
  agent_id: agent.id,
  goal: 'A previous dinner booking',
  status: 'done',
  summary: 'Reservation confirmed by backend.',
  created_at: '2026-10-24T10:00:00Z',
  events: [],
});
async function backend(page: Page, initial: Task[] = []) {
  const state = {
    agents: structuredClone([agent]),
    tasks: structuredClone(initial),
    failChat: false,
    failPatch: false,
    failDelete: false,
    failHangUp: false,
    hungUp: [] as string[],
    unavailable: new Set<string>(),
    lastMessage: {} as Record<string, unknown>,
  };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    if (path === '/api/agents') {
      if (method === 'POST') {
        const created = { ...route.request().postDataJSON(), id: `copy-${state.agents.length}` };
        state.agents.push(created);
        return route.fulfill({ json: created });
      }
      return route.fulfill({ json: state.agents });
    }
    const agentMatch = path.match(/^\/api\/agents\/([^/]+)$/);
    if (agentMatch) {
      const current = state.agents.find((a) => a.id === agentMatch[1]);
      if (method === 'PATCH') {
        if (state.failPatch)
          return route.fulfill({ status: 503, json: { detail: 'Could not save changes.' } });
        Object.assign(current!, route.request().postDataJSON());
        return route.fulfill({ json: current });
      }
      if (method === 'DELETE') {
        if (state.failDelete)
          return route.fulfill({
            status: 409,
            json: { detail: 'An active task appeared. Try again later.' },
          });
        state.agents = state.agents.filter((a) => a.id !== agentMatch[1]);
        return route.fulfill({ status: 204 });
      }
    }
    const taskList = path.match(/^\/api\/agents\/([^/]+)\/tasks$/);
    if (taskList)
      return state.unavailable.has(taskList[1])
        ? route.fulfill({ status: 503, json: { detail: 'Tasks unavailable' } })
        : route.fulfill({ json: state.tasks.filter((t) => t.agent_id === taskList[1]) });
    if (path.endsWith('/chat')) {
      state.lastMessage = route.request().postDataJSON();
      if (state.failChat)
        return route.fulfill({
          status: 503,
          json: { detail: 'Agent is temporarily unavailable.' },
        });
      const id = `task-${state.tasks.length}`;
      state.tasks.push({
        id,
        agent_id: agent.id,
        goal: String(state.lastMessage.message),
        status: 'awaiting_approval',
        created_at: new Date().toISOString(),
        events: [],
        call: {
          id: `call-${id}`,
          status: 'answered',
          started_at: new Date().toISOString(),
          transcript: [],
        },
        payment: {
          id: `payment-${id}`,
          task_id: id,
          amount: 2000,
          currency: 'GBP',
          status: 'pending_approval',
        },
      });
      return route.fulfill({ json: { task_id: id } });
    }
    if (/\/payments\/.*\/(approve|deny)$/.test(path)) {
      const task = state.tasks.find((t) => t.payment?.id === path.split('/')[3])!;
      task.status = 'done';
      task.summary = path.endsWith('/approve')
        ? 'Reservation confirmed by backend.'
        : 'Payment declined.';
      task.payment!.status = path.endsWith('/approve') ? 'paid' : 'denied';
      task.call!.ended_at = new Date().toISOString();
      task.call!.transcript = [
        { speaker: 'Restaurant', text: 'Live backend transcript received.' },
      ];
      return route.fulfill({ status: 204 });
    }
    const hangUp = path.match(/^\/api\/calls\/([^/]+)\/hang-up$/);
    if (hangUp) {
      if (state.failHangUp)
        return route.fulfill({
          status: 503,
          json: { detail: 'This call can’t be hung up from here. Hang up on the phone instead.' },
        });
      state.hungUp.push(hangUp[1]);
      const task = state.tasks.find((t) => t.call?.id === hangUp[1])!;
      task.status = 'failed';
      task.summary = 'You hung up the call before it finished.';
      task.call!.ended_at = new Date().toISOString();
      return route.fulfill({ status: 202, json: { status: 'hanging_up' } });
    }
    const detail = path.match(/^\/api\/tasks\/([^/]+)$/);
    if (detail) {
      const task = state.tasks.find((t) => t.id === detail[1]);
      return task
        ? route.fulfill({ json: task })
        : route.fulfill({ status: 404, json: { detail: 'Task not found.' } });
    }
    if (path.endsWith('/events/stream')) {
      const event = {
        ts: '2026-10-24T12:00:00Z',
        call_id: path.split('/')[3],
        kind: 'transcript_line',
        payload: { speaker: 'Restaurant', text: 'Live backend transcript received.' },
      };
      return route.fulfill({
        contentType: 'text/event-stream',
        body: `id: 1\nevent: transcript_line\ndata: ${JSON.stringify(event)}\n\n`,
      });
    }
    return route.fulfill({ status: 404, json: { detail: 'Unknown endpoint' } });
  });
  return state;
}
test('HTTP adapter, named SSE, approval, reload, and no demo metadata on the wire', async ({
  page,
}) => {
  const state = await backend(page);
  await page.goto(`/chat/${agent.id}`);
  await expect(page.getByText('Demo · simulated')).toHaveCount(0);
  await expect(page.getByLabel('Demo scenario')).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Message Maya' }).fill('Book dinner');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Live backend transcript received.')).toBeVisible();
  expect(state.lastMessage).toEqual({ message: 'Book dinner' });
  await page.getByRole('button', { name: 'Approve £20.00' }).click();
  await expect(page.getByText('Reservation confirmed by backend.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Reservation confirmed by backend.')).toBeVisible();
});
test('Hang up ends a live call, and explains when it cannot', async ({ page }) => {
  const state = await backend(page);
  state.failHangUp = true;
  await page.goto(`/chat/${agent.id}`);
  await page.getByRole('textbox', { name: 'Message Maya' }).fill('Book dinner');
  await page.getByRole('button', { name: 'Send message' }).click();
  const hangUp = page.getByRole('button', { name: 'Hang up' });
  await expect(hangUp).toBeVisible();
  await hangUp.scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'test-results/hang-up-button.png' });
  await hangUp.click();
  await expect(page.getByRole('alert')).toContainText('Hang up on the phone instead.');
  state.failHangUp = false;
  await hangUp.click();
  await expect(page.getByText('You hung up the call before it finished.')).toBeVisible();
  await expect(page.getByRole('button', { name: /Hang up|Hanging up/ })).toHaveCount(0);
  expect(state.hungUp).toEqual(['call-task-0']);
});
test('failed sends preserve the draft for a deliberate retry', async ({ page }) => {
  const state = await backend(page);
  state.failChat = true;
  await page.goto(`/chat/${agent.id}`);
  const composer = page.getByRole('textbox', { name: 'Message Maya' });
  await composer.fill('Please book dinner');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByRole('alert')).toContainText('Agent is temporarily unavailable.');
  await expect(composer).toHaveValue('Please book dinner');
  state.failChat = false;
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByRole('button', { name: 'Approve £20.00' })).toBeVisible();
});
test('permissions save failures do not enter the agent or discard choices', async ({ page }) => {
  const state = await backend(page);
  state.failPatch = true;
  await page.goto('/');
  await page.getByRole('checkbox', { name: 'Phone calls', exact: true }).uncheck();
  await page.getByRole('button', { name: 'Enter agent', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Could not save changes.');
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('checkbox', { name: 'Phone calls', exact: true })).not.toBeChecked();
  state.failPatch = false;
  await page.getByRole('button', { name: 'Enter agent', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/chat/${agent.id}$`));
  expect(state.agents[0].tools).toEqual(['payments', 'calendar']);
});
test('history loads server tasks on a fresh browser and preserves partial results', async ({
  page,
}) => {
  const state = await backend(page, [finished()]);
  state.agents.push({ ...agent, id: 'other', name: 'Other' });
  state.unavailable.add('other');
  await page.goto('/history');
  await expect(page.getByRole('link', { name: /A previous dinner booking/ })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Some agents');
  await page.getByRole('link', { name: /A previous dinner booking/ }).click();
  await expect(page.getByText('Reservation confirmed by backend.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Reservation confirmed by backend.')).toBeVisible();
});
test('profile update failure keeps the form, then saves and duplicates independently', async ({
  page,
}) => {
  const state = await backend(page);
  state.failPatch = true;
  await page.goto('/');
  await page.getByText('Manage', { exact: true }).click();
  await page.getByRole('button', { name: 'Edit agent', exact: true }).click();
  await page.getByRole('textbox', { name: 'Agent name' }).fill('Maya edited');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByRole('alert')).toContainText('Could not save changes.');
  await expect(page.getByRole('textbox', { name: 'Agent name' })).toHaveValue('Maya edited');
  state.failPatch = false;
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByRole('heading', { name: 'Maya edited', exact: true })).toBeVisible();
  await page.getByLabel('Manage agent').click();
  await page.getByRole('button', { name: 'Duplicate agent', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Duplicate agent', exact: true })
    .click();
  await expect(page.getByRole('heading', { name: 'Maya edited copy', exact: true })).toBeVisible();
  expect(state.agents).toHaveLength(2);
});
test('server deletion conflict is handled and a later delete preserves archived history', async ({
  page,
}) => {
  const state = await backend(page, [finished()]);
  state.failDelete = true;
  await page.goto('/');
  await page.getByLabel('Manage agent').click();
  await page.getByRole('button', { name: 'Delete agent', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete agent', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('An active task appeared.');
  state.failDelete = false;
  await page.getByRole('dialog').getByRole('button', { name: 'Delete agent', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Create your first agent' })).toBeVisible();
  await page.goto('/history');
  await page.getByRole('link', { name: /A previous dinner booking/ }).click();
  await expect(page.getByText('Archived copy saved in this browser.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Reservation confirmed by backend.')).toBeVisible();
});
