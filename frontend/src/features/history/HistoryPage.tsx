import { useState } from 'react';
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, History, Search } from 'lucide-react';
import { api } from '../../api';
import { dateTime, labels } from '../../config';
import { isActive } from '../../history-types';
import { useAgents } from '../../state';
import { Avatar, Empty, ErrorNotice, Loading, PageHeading } from '../../components/ui';
import { TaskCard } from '../../components/TaskCard';
export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const [limit, setLimit] = useState(20);
  const query = useQuery({ queryKey: ['history'], queryFn: api.history, refetchInterval: 2000 });
  const search = params.get('q') || '';
  const status = params.get('status') || '';
  const selectedAgent = params.get('agent') || '';
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
    setLimit(20);
  }
  const items = query.data?.items || [];
  const agents = [...new Map(items.map((entry) => [entry.agent.id, entry.agent])).values()];
  const needle = search.toLocaleLowerCase().trim();
  const filtered = items
    .filter(
      ({ task, agent }) =>
        (!status || task.status === status) &&
        (!selectedAgent || task.agent_id === selectedAgent) &&
        (!needle ||
          [
            task.goal,
            task.summary,
            agent.name,
            ...(task.call?.transcript || []).map((line) => line.text),
          ]
            .filter(Boolean)
            .join(' ')
            .toLocaleLowerCase()
            .includes(needle)),
    )
    .sort(
      (a, b) =>
        Date.parse(b.task.created_at) - Date.parse(a.task.created_at) ||
        b.task.id.localeCompare(a.task.id),
    );
  return (
    <div className="page history-page">
      <PageHeading title="Task history" description="Find a request, transcript, or booking." />
      <div className="history-filters">
        <label className="history-search">
          <Search size={18} />
          <span className="sr-only">Search history</span>
          <input
            value={search}
            onChange={(event) => filter('q', event.target.value)}
            placeholder="Search tasks or transcripts"
          />
        </label>
        <label>
          <span className="sr-only">Filter by status</span>
          <select value={status} onChange={(event) => filter('status', event.target.value)}>
            <option value="">All statuses</option>
            {Object.entries(labels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by agent</span>
          <select value={selectedAgent} onChange={(event) => filter('agent', event.target.value)}>
            <option value="">All agents</option>
            {agents.map((agent) => (
              <option value={agent.id} key={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => query.refetch()} />
      ) : (
        <>
          {!!query.data?.unavailable.length && (
            <div className="error-notice" role="alert">
              <span>Some agents’ tasks could not be loaded. Available tasks are shown below.</span>
              <button className="text-button" onClick={() => query.refetch()}>
                Retry
              </button>
              <details>
                <summary>Details</summary>
                {query.data.unavailable.map((item) => (
                  <p key={item.id}>{item.message}</p>
                ))}
              </details>
            </div>
          )}
          {query.data && !query.data.persistent && (
            <p className="info-box" role="status">
              Browser storage is unavailable. Archived tasks may not survive a reload.
            </p>
          )}
          {filtered.length ? (
            <>
              <p className="history-count" role="status">
                {filtered.length} {filtered.length === 1 ? 'task' : 'tasks'}
              </p>
              <div className="history-list">
                {filtered.slice(0, limit).map(({ task, agent, archived }) => (
                  <Link
                    className="history-row"
                    key={task.id}
                    to={`/history/${encodeURIComponent(task.id)}${params.size ? `?${params}` : ''}`}
                  >
                    <Avatar agent={agent} small />
                    <div className="history-row-body">
                      <h2>{task.goal}</h2>
                      <p>{task.summary || labels[task.status]}</p>
                      <small>
                        {agent.name} · {dateTime(task.created_at)}
                        {archived ? ' · Archived copy' : ''}
                      </small>
                    </div>
                    <span className={`status-chip ${task.status}`}>{labels[task.status]}</span>
                    <ArrowRight size={17} />
                  </Link>
                ))}
              </div>
              {filtered.length > limit && (
                <button
                  className="secondary load-more"
                  onClick={() => setLimit((value) => value + 20)}
                >
                  Show more tasks
                </button>
              )}
            </>
          ) : (
            <Empty
              icon={<History size={27} />}
              title={
                search || status || selectedAgent
                  ? 'No matching tasks'
                  : query.data?.unavailable.length
                    ? 'Tasks could not be loaded'
                    : 'No tasks yet'
              }
            >
              {search || status || selectedAgent ? (
                <button
                  className="text-button"
                  onClick={() => {
                    setParams({});
                    setLimit(20);
                  }}
                >
                  Clear filters
                </button>
              ) : query.data?.unavailable.length ? (
                'Retry to load your task history.'
              ) : (
                <Link className="text-button" to="/chat">
                  Start a chat <ArrowRight size={15} />
                </Link>
              )}
            </Empty>
          )}
        </>
      )}
    </div>
  );
}
export function TaskDetailPage() {
  const { taskId = '' } = useParams();
  const location = useLocation();
  const agents = useAgents();
  const query = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.taskDetail(taskId),
    refetchInterval: (q) => (q.state.data && !isActive(q.state.data.task) ? false : 1200),
  });
  return (
    <div className="page task-detail-page">
      <Link className="back-link" to={`/history${location.search}`}>
        <ArrowLeft size={16} /> Back to history
      </Link>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => query.refetch()} />
      ) : (
        <>
          <PageHeading
            title={query.data.task.goal}
            description={`${query.data.agent.name} · ${dateTime(query.data.task.created_at)}`}
            action={
              agents.data?.some((a) => a.id === query.data.task.agent_id) ? (
                <Link className="secondary" to={`/chat/${query.data.task.agent_id}`}>
                  Open chat <ArrowRight size={16} />
                </Link>
              ) : undefined
            }
          />
          {query.data.archived && (
            <p className="archive-note">Archived copy saved in this browser.</p>
          )}
          <TaskCard task={query.data.task} agent={query.data.agent} />
        </>
      )}
    </div>
  );
}
