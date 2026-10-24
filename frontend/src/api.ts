import { demo } from './demo';
import type { Agent, AgentInput, Analytics, CalendarEvent, Task } from './types';
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
const refsKey = 'concierge-api-tasks-v1';
function refs(): { id: string; agent_id: string }[] {
  try {
    return JSON.parse(localStorage.getItem(refsKey) || '[]');
  } catch {
    return [];
  }
}
export const api = {
  agents: (): Promise<Agent[]> => (DEMO ? demo.agents() : request('/agents')),
  createAgent: (input: AgentInput): Promise<Agent> =>
    DEMO
      ? demo.createAgent(input)
      : request('/agents', { method: 'POST', body: JSON.stringify(input) }),
  tasks: async (agentId: string): Promise<Task[]> => {
    if (DEMO) return Promise.all((await demo.tasks(agentId)).map((t) => demo.task(t.id)));
    return Promise.all(
      refs()
        .filter((t) => t.agent_id === agentId)
        .map((t) => request<Task>(`/tasks/${encodeURIComponent(t.id)}`)),
    );
  },
  send: async (agentId: string, message: string) => {
    if (DEMO) return demo.send(agentId, message);
    const result = await request<{ task_id: string }>(
      `/agents/${encodeURIComponent(agentId)}/chat`,
      { method: 'POST', body: JSON.stringify({ message }) },
    );
    try {
      localStorage.setItem(
        refsKey,
        JSON.stringify([...refs(), { id: result.task_id, agent_id: agentId }]),
      );
    } catch {
      throw new Error(
        'Task started, but browser storage is unavailable. Task ID: ' + result.task_id,
      );
    }
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
