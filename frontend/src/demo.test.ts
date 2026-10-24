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
  it('holds the task until explicit approval, then creates the calendar event', async () => {
    let task = await booking();
    expect(task.status).toBe('awaiting_approval');
    expect(task.payment?.status).toBe('pending_approval');
    expect(await demo.calendar()).toEqual([]);
    vi.advanceTimersByTime(60000);
    task = await demo.task(task.id);
    expect(task.status).toBe('awaiting_approval');
    await demo.decide(task.payment!.id, true);
    task = await demo.task(task.id);
    expect(task.status).toBe('done');
    expect(task.payment?.status).toBe('paid');
    expect(await demo.calendar()).toHaveLength(1);
    expect((await demo.analytics()).success_rate).toBe(100);
    await expect(demo.decide(task.payment!.id, true)).rejects.toThrow('already been handled');
  });
  it('declining never creates a reservation and is not counted as success', async () => {
    const task = await booking();
    await demo.decide(task.payment!.id, false);
    expect((await demo.task(task.id)).payment?.status).toBe('denied');
    expect(await demo.calendar()).toHaveLength(0);
    expect((await demo.analytics()).success_rate).toBe(0);
  });
  it('does not use disabled tools', async () => {
    const input: AgentInput = {
      name: 'Minimal',
      persona: 'Help me',
      voice: 'Calm',
      tools: ['email'],
    };
    const agent = await demo.createAgent(input);
    const { task_id } = await demo.send(agent.id, 'Organise my schedule');
    vi.advanceTimersByTime(2000);
    const task = await demo.task(task_id);
    expect(task.status).toBe('done');
    expect(task.call).toBeUndefined();
    expect(task.payment).toBeUndefined();
    expect(task.calendar_event).toBeUndefined();
  });
  it('shows failure instead of booking a deposit without a payment tool', async () => {
    const agent = await demo.createAgent({
      name: 'Phone only',
      persona: 'Calls',
      voice: 'Warm',
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
    vi.advanceTimersByTime(2000);
    expect((await demo.task(task_id)).status).toBe('failed');
    expect(await demo.calendar()).toEqual([]);
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
    expect(task.calendar_event).toBeUndefined();
  });
});
