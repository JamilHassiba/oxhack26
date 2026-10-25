import { useQuery } from '@tanstack/react-query';
import { api } from './api';
export function useAgents() {
  return useQuery({ queryKey: ['agents'], queryFn: api.agents });
}
export function useTasks(agentId: string) {
  return useQuery({
    queryKey: ['tasks', agentId],
    queryFn: () => api.tasks(agentId),
    enabled: !!agentId,
    refetchInterval: 1200,
    refetchIntervalInBackground: true,
  });
}
