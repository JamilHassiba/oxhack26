import { demo } from './demo';
import type { Agent, AgentInput, Analytics, CalendarEvent, Task, Tool } from './types';
import type { HistoryEntry, TaskHistory } from './history-types';
import { isActive, previousAgent } from './history-types';
import { archivedHistory, archiveHistory, archivePersistent } from './history-archive';
export const DEMO = import.meta.env.VITE_DEMO_MODE !== 'false';
export const BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
    signal: init?.signal || AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      typeof error?.detail === 'string'
        ? error.detail
        : `Request failed (${response.status}). Please try again.`,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
const knownAgents = new Map<string, Agent>();
export const api = {
  agents: async (): Promise<Agent[]> => {
    const agents = DEMO ? await demo.agents() : await request<Agent[]>('/agents');
    agents.forEach((agent) => knownAgents.set(agent.id, agent));
    return agents;
  },
  createAgent: (input: AgentInput): Promise<Agent> =>
    DEMO
      ? demo.createAgent(input)
      : request('/agents', { method: 'POST', body: JSON.stringify(input) }),
  updateAgent: (id: string, input: Partial<AgentInput>): Promise<Agent> =>
    DEMO
      ? demo.updateAgent(id, input)
      : request(`/agents/${encodeURIComponent(id)}`, {
          method: 'PATCH',
          body: JSON.stringify(input),
        }),
  setAgentTools: (id: string, tools: Tool[]): Promise<Agent> => api.updateAgent(id, { tools }),
  deleteAgent: async (id: string): Promise<void> => {
    if (DEMO) return demo.deleteAgent(id);
    const tasks = await api.tasks(id);
    if (tasks.some(isActive))
      throw new Error('Finish this agent’s active tasks and payment approvals before deleting it.');
    const agent = knownAgents.get(id) || previousAgent(id);
    await request(`/agents/${encodeURIComponent(id)}`, { method: 'DELETE' });
    archiveHistory(tasks.map((task) => ({ task, agent })));
  },
  history: async (): Promise<TaskHistory> => {
    if (DEMO) return demo.history();
    const agents = await api.agents();
    const results = await Promise.allSettled(agents.map((agent) => api.tasks(agent.id)));
    const items: HistoryEntry[] = archivedHistory();
    const unavailable: TaskHistory['unavailable'] = [];
    results.forEach((result, index) => {
      const agent = agents[index];
      if (result.status === 'fulfilled')
        items.push(...result.value.map((task) => ({ task, agent })));
      else
        unavailable.push({
          id: agent.id,
          message: `${agent.name}: ${result.reason instanceof Error ? result.reason.message : 'Could not load tasks.'}`,
        });
    });
    return {
      items: [...new Map(items.map((entry) => [entry.task.id, entry])).values()],
      unavailable,
      scope: 'server',
      persistent: archivePersistent(),
    };
  },
  taskDetail: async (id: string): Promise<HistoryEntry> => {
    if (DEMO) return demo.taskDetail(id);
    const archived = archivedHistory().find((entry) => entry.task.id === id);
    if (archived) return archived;
    const task = await request<Task>(`/tasks/${encodeURIComponent(id)}`);
    if (!knownAgents.has(task.agent_id)) await api.agents().catch(() => undefined);
    return { task, agent: knownAgents.get(task.agent_id) || previousAgent(task.agent_id) };
  },
  tasks: async (agentId: string): Promise<Task[]> =>
    DEMO
      ? Promise.all((await demo.tasks(agentId)).map((t) => demo.task(t.id)))
      : request(`/agents/${encodeURIComponent(agentId)}/tasks`),
  send: async (agentId: string, message: string) => {
    if (DEMO) return demo.send(agentId, message);
    const result = await request<{ task_id: string }>(
      `/agents/${encodeURIComponent(agentId)}/chat`,
      { method: 'POST', body: JSON.stringify({ message }) },
    );
    return result;
  },
  decide: (id: string, approve: boolean) =>
    DEMO
      ? demo.decide(id, approve)
      : request<void>(`/payments/${encodeURIComponent(id)}/${approve ? 'approve' : 'deny'}`, {
          method: 'POST',
        }),
  calendar: (): Promise<CalendarEvent[]> => (DEMO ? demo.calendar() : request('/calendar')),
  analytics: (): Promise<Analytics> => (DEMO ? demo.analytics() : request('/analytics/summary')),
};
function escapeIcs(value: string) {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/\r?\n/g, '\\n')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,');
}
export function calendarIcs(events: CalendarEvent[]) {
  const date = (s: string) =>
    new Date(s)
      .toISOString()
      .replace(/[-:]/g, '')
      .replace(/\.\d{3}Z/, 'Z');
  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Concierge//Calendar//EN',
    ...events.flatMap((e) => [
      'BEGIN:VEVENT',
      `UID:${escapeIcs(e.id)}@concierge`,
      `DTSTAMP:${date(new Date().toISOString())}`,
      `DTSTART:${date(e.starts_at)}`,
      `DTEND:${date(e.ends_at)}`,
      `SUMMARY:${escapeIcs(e.title)}`,
      `LOCATION:${escapeIcs(e.location)}`,
      'END:VEVENT',
    ]),
    'END:VCALENDAR',
    '',
  ].join('\r\n');
}
export function downloadCalendar(events: CalendarEvent[]) {
  if (!DEMO) {
    window.location.assign(`${BASE}/calendar.ics`);
    return;
  }
  const url = URL.createObjectURL(
    new Blob([calendarIcs(events)], { type: 'text/calendar;charset=utf-8' }),
  );
  const a = document.createElement('a');
  a.href = url;
  a.download = 'concierge.ics';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
