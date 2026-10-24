import { useQueries, useQuery } from '@tanstack/react-query';
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
export function useWorkspaceTasks() {
  const agents = useAgents();
  const queries = useQueries({
    queries: (agents.data || []).map((agent) => ({
      queryKey: ['tasks', agent.id],
      queryFn: () => api.tasks(agent.id),
      refetchInterval: 1200,
    })),
  });
  return {
    tasks: queries.flatMap((q) => q.data || []),
    isPending: agents.isPending || queries.some((q) => q.isPending),
    error: agents.error || queries.find((q) => q.error)?.error,
    retry: () => {
      agents.refetch();
      queries.forEach((q) => q.refetch());
    },
  };
}
