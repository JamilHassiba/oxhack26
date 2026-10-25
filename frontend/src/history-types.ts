import type { Agent, Task } from './types';
// UI projections, separate from FastAPI's task schema.
export type HistoryEntry = { task: Task; agent: Agent; archived?: boolean };
export type TaskHistory = {
  items: HistoryEntry[];
  unavailable: { id: string; message: string }[];
  scope: 'demo' | 'server';
  persistent: boolean;
};
export function previousAgent(id: string): Agent {
  return { id, name: 'Previous agent', tools: [] };
}
export function isActive(task: Task) {
  return !['done', 'failed'].includes(task.status);
}
