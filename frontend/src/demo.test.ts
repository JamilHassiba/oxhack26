// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AgentInput } from './types';
let demo: typeof import('./demo').demo;
beforeEach(async () => {
  const storage = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => storage.get(key) || null,
    setItem: (key: string, value: string) => storage.set(key, value),
  });
  vi.useFakeTimers();
  vi.resetModules();
  demo = (await import('./demo')).demo;
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
async function booking() {
  const { task_id } = await demo.send('maya', 'Book dinner');
  vi.advanceTimersByTime(7000);
  return demo.task(task_id);
}
describe('demo booking lifecycle', () => {
  it('holds the task until explicit approval, then confirms the booking', async () => {
    let task = await booking();
    expect(task.status).toBe('awaiting_approval');
    expect(task.payment?.status).toBe('pending_approval');
    vi.advanceTimersByTime(60000);
    task = await demo.task(task.id);
    expect(task.status).toBe('awaiting_approval');
    await demo.decide(task.payment!.id, true);
    task = await demo.task(task.id);
    expect(task.status).toBe('done');
    expect(task.payment?.status).toBe('paid');
    expect(task.call?.outcome?.booked).toBe(true);
    await expect(demo.decide(task.payment!.id, true)).rejects.toThrow('already been handled');
  });
  it('declining never creates a reservation and is not counted as success', async () => {
    const task = await booking();
    await demo.decide(task.payment!.id, false);
    expect((await demo.task(task.id)).payment?.status).toBe('denied');
    expect((await demo.task(task.id)).call?.outcome?.booked).toBe(false);
  });
  it('does not use disabled tools', async () => {
    const input: AgentInput = {
      name: 'Minimal',
      tools: ['email'],
    };
    const agent = await demo.createAgent(input);
    const { task_id } = await demo.send(agent.id, 'Organise my schedule');
    vi.advanceTimersByTime(2000);
    const task = await demo.task(task_id);
    expect(task.status).toBe('done');
    expect(task.call).toBeUndefined();
    expect(task.payment).toBeUndefined();
  });
  it('shows failure instead of booking a deposit without a payment tool', async () => {
    const agent = await demo.createAgent({
      name: 'Phone only',
      tools: ['phone'],
    });
    const { task_id } = await demo.send(agent.id, 'Book dinner');
    vi.advanceTimersByTime(7000);
    const task = await demo.task(task_id);
    expect(task.status).toBe('failed');
    expect(task.payment).toBeUndefined();
    expect(task.call?.ended_at).toBeTruthy();
  });
  it('handles a no-answer scenario', async () => {
    const { task_id } = await demo.send('maya', 'no answer');
    vi.advanceTimersByTime(7000);
    expect((await demo.task(task_id)).status).toBe('failed');
  });
  it('persists agents and task state across module reloads', async () => {
    const task = await booking();
    vi.resetModules();
    const restored = (await import('./demo')).demo;
    expect((await restored.task(task.id)).status).toBe('awaiting_approval');
  });
});

describe('agent permissions', () => {
  it('persists changed tools and respects them for the next task', async () => {
    await demo.setAgentTools('maya', ['email']);
    vi.resetModules();
    const restored = (await import('./demo')).demo;
    expect((await restored.agents()).find((a) => a.id === 'maya')?.tools).toEqual(['email']);
    const { task_id } = await restored.send('maya', 'Help with my request');
    vi.advanceTimersByTime(2000);
    const task = await restored.task(task_id);
    expect(task.call).toBeUndefined();
    expect(task.payment).toBeUndefined();
  });
});

describe('rehearsal scenarios and history', () => {
  it('records a no-answer call as a failed outcome and never creates a deposit', async () => {
    const { task_id } = await demo.send('maya', 'Call the restaurant', 'no_answer');
    vi.advanceTimersByTime(7000);
    const task = await demo.task(task_id);
    expect(task.status).toBe('failed');
    expect(task.call?.ended_at).toBeTruthy();
    expect(task.call?.transcript).toEqual([]);
    expect(task.payment).toBeUndefined();
  });
  it('fully booked produces a transcript and no payment', async () => {
    const { task_id } = await demo.send('maya', 'Book dinner', 'fully_booked');
    vi.advanceTimersByTime(7000);
    const task = await demo.task(task_id);
    expect(task.status).toBe('failed');
    expect(task.summary).toContain('fully booked');
    expect(task.call?.transcript.at(-1)?.text).toContain('fully booked');
    expect(task.payment).toBeUndefined();
  });
  it('books the agreed fallback at 19:00 with no unnecessary charge', async () => {
    const { task_id } = await demo.send('maya', '7pm is fine', 'alternative_time');
    vi.advanceTimersByTime(7000);
    const task = await demo.task(task_id);
    expect(task.status).toBe('done');
    expect(task.summary).toContain('19:00');
    expect(task.payment).toBeUndefined();
    expect(task.call?.outcome?.starts_at).toMatch(/T19:00$/);
    const again = await demo.task(task_id);
    expect(again.events).toEqual(task.events);
  });
  it('declined-deposit rehearsal waits for the user instead of auto-denying', async () => {
    const { task_id } = await demo.send('maya', 'Book dinner', 'declined_deposit');
    vi.advanceTimersByTime(7000);
    let task = await demo.task(task_id);
    expect(task.payment?.status).toBe('pending_approval');
    vi.advanceTimersByTime(120000);
    task = await demo.task(task_id);
    expect(task.status).toBe('awaiting_approval');
    await demo.decide(task.payment!.id, false);
    expect((await demo.task(task_id)).payment?.status).toBe('denied');
  });
  it('edits do not change a run already in progress, and deletion waits for resolution', async () => {
    const { task_id } = await demo.send('maya', 'Book dinner');
    await demo.updateAgent('maya', { name: 'Maya updated', tools: [] });
    await expect(demo.deleteAgent('maya')).rejects.toThrow('active tasks');
    vi.advanceTimersByTime(7000);
    const task = await demo.task(task_id);
    expect(task.payment?.status).toBe('pending_approval');
    expect(task.call?.transcript[0].speaker).toBe('Maya');
    await expect(demo.deleteAgent('maya')).rejects.toThrow('payment approvals');
    await demo.decide(task.payment!.id, true);
    await demo.deleteAgent('maya');
    expect((await demo.agents()).map((a) => a.id)).not.toContain('maya');
  });
  it('rejects overlapping runs and invalid scenario IDs', async () => {
    await expect(demo.send('maya', 'Book dinner', 'not-a-scenario' as never)).rejects.toThrow(
      'Unknown demo scenario',
    );
    await demo.send('maya', 'Book dinner');
    await expect(demo.send('maya', 'Another booking')).rejects.toThrow('current task');
  });
  it('works in memory when browser storage is unavailable', async () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('Unavailable');
      },
      setItem: () => {
        throw new Error('Unavailable');
      },
    });
    await demo.createAgent({ name: 'Private browser', tools: [] });
    const { task_id } = await demo.send('maya', 'Book dinner', 'alternative_time');
    vi.advanceTimersByTime(7000);
    expect((await demo.task(task_id)).status).toBe('done');
  });
});
