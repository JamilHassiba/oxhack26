import type { HistoryEntry } from './history-types';
const key = 'concierge-archived-history-v1';
let memory: HistoryEntry[] | undefined;
let persistent = true;
export function archivedHistory(): HistoryEntry[] {
  if (!memory) {
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(key) || '[]');
      memory = Array.isArray(saved)
        ? saved.filter(
            (e): e is HistoryEntry =>
              !!e && typeof e.task?.id === 'string' && typeof e.agent?.id === 'string',
          )
        : [];
    } catch {
      memory = [];
      persistent = false;
    }
  }
  return structuredClone(memory);
}
export function archiveHistory(entries: HistoryEntry[]) {
  const unique = new Map(archivedHistory().map((entry) => [entry.task.id, entry]));
  entries.forEach((entry) =>
    unique.set(entry.task.id, { ...structuredClone(entry), archived: true }),
  );
  memory = [...unique.values()];
  try {
    localStorage.setItem(key, JSON.stringify(memory));
    persistent = true;
  } catch {
    persistent = false;
  }
}
export function archivePersistent() {
  return persistent;
}
