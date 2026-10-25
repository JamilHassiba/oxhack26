import { demo } from './demo';
import type { Agent, AgentInput, Task, Tool } from './types';
import { isActive } from './config';
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
export const api = {
  agents: (): Promise<Agent[]> => (DEMO ? demo.agents() : request('/agents')),
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
    await request(`/agents/${encodeURIComponent(id)}`, { method: 'DELETE' });
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
  hangUp: (callId: string) =>
    request<void>(`/calls/${encodeURIComponent(callId)}/hang-up`, { method: 'POST' }),
};
