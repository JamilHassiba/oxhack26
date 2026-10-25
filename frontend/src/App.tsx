import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  Link,
  Navigate,
  Route,
  Routes,
  useParams,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  ArrowUp,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Clock3,
  CreditCard,
  LoaderCircle,
  MessageSquare,
  Phone,
  Plus,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { api, DEMO } from './api';
import { tools, shortcuts, dateTime } from './config';
import { Avatar, ErrorNotice, Loading, Empty, PageHeading } from './components/ui';
import { TaskCard, PaymentCard } from './components/TaskCard';
import { useAgents, useTasks, useWorkspaceTasks } from './state';
import { AgentEditor } from './features/agents/AgentEditor';
import type { Agent, Tool } from './types';
import { AgentActions } from './features/agents/AgentActions';
import { HistoryPage, TaskDetailPage } from './features/history/HistoryPage';
export default function App() {
  // No sidebar: the logo is the one way home, the home page is the agents page, and chats are
  // entered from there. History, payments and analytics still work by URL.
  return (
    <div className="app-shell">
      <div className="main-shell">
        <header className="topbar">
          <Link to="/" className="brand brand-button" aria-label="concierge. Home">
            <span className="brand-mark">
              <Sparkles size={20} />
            </span>
            concierge<span className="brand-dot">.</span>
          </Link>
          {DEMO && (
            <span className="mode-badge">
              <span /> Demo · simulated
            </span>
          )}
        </header>
        <main>
          <Routes>
            <Route path="/" element={<AgentsPage />} />
            <Route path="/agents" element={<Navigate to="/" replace />} />
            <Route path="/chat" element={<ChatRedirect />} />
            <Route path="/chat/:agentId" element={<ChatPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/history/:taskId" element={<TaskDetailPage />} />
            <Route path="/payments" element={<PaymentsPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
function AgentsPage() {
  const query = useAgents();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    try {
      return localStorage.getItem('concierge-selected-agent-v1');
    } catch {
      return null;
    }
  });
  function selectAgent(id: string) {
    setSelectedId(id);
    try {
      localStorage.setItem('concierge-selected-agent-v1', id);
    } catch {
      /* Selection still works without storage. */
    }
  }
  const [drafts, setDrafts] = useState<Record<string, Tool[]>>({});
  const agents = query.data || [];
  const index = Math.max(
    0,
    agents.findIndex((agent) => agent.id === selectedId),
  );
  const agent = agents[index];
  const enabled = agent ? drafts[agent.id] || agent.tools : [];
  const enter = useMutation({
    mutationFn: async ({ agent, tools: selectedTools }: { agent: Agent; tools: Tool[] }) => {
      const changed =
        selectedTools.length !== agent.tools.length ||
        selectedTools.some((tool) => !agent.tools.includes(tool));
      return changed ? api.setAgentTools(agent.id, selectedTools) : agent;
    },
    onSuccess: (updated) => {
      client.setQueryData<Agent[]>(['agents'], (old) =>
        old?.map((agent) => (agent.id === updated.id ? updated : agent)),
      );
      client.invalidateQueries({ queryKey: ['agents'] });
      navigate(`/chat/${updated.id}`);
    },
  });
  function switchAgent(direction: number) {
    selectAgent(agents[(index + direction + agents.length) % agents.length].id);
    enter.reset();
  }
  return (
    <div className="page agent-selection-page">
      <PageHeading
        title="Your agents"
        action={
          // With no agents the empty state has its own Create agent button; one is enough.
          agents.length > 0 && (
            <button className="secondary create-agent-button" onClick={() => setCreating(true)}>
              <Plus size={17} /> <span>Create agent</span>
            </button>
          )
        }
      />
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => query.refetch()} />
      ) : agent ? (
        <section className="agent-picker" aria-label="Agent selection">
          <button
            className="agent-arrow previous"
            aria-label="Previous agent"
            onClick={() => switchAgent(-1)}
            disabled={agents.length < 2 || enter.isPending}
          >
            <ChevronLeft size={25} />
          </button>
          <article className="selected-agent" aria-label={`${agent.name} permissions`}>
            <AgentActions
              key={agent.id}
              agent={{ ...agent, tools: enabled }}
              disabled={enter.isPending}
              onSaved={(saved) => {
                selectAgent(saved.id);
                setDrafts((old) => {
                  const next = { ...old };
                  delete next[saved.id];
                  return next;
                });
                enter.reset();
              }}
              onDeleted={() => {
                const remaining = agents.filter((a) => a.id !== agent.id);
                selectAgent(remaining[Math.min(index, remaining.length - 1)]?.id || '');
                enter.reset();
              }}
            />
            <div className="selected-agent-identity">
              <Avatar agent={agent} />
              <h2>{agent.name}</h2>
            </div>
            <fieldset className="agent-permissions" disabled={enter.isPending}>
              <legend>Allowed tools</legend>
              <div className="permission-grid">
                {Object.entries(tools).map(([key, tool]) => {
                  const Icon = tool.icon;
                  const checked = enabled.includes(key as Tool);
                  return (
                    <label key={key} className={`permission-row ${checked ? 'selected' : ''}`}>
                      <Icon size={20} />
                      <span>{tool.label}</span>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) =>
                          setDrafts((old) => ({
                            ...old,
                            [agent.id]: event.target.checked
                              ? [...enabled, key as Tool]
                              : enabled.filter((t) => t !== key),
                          }))
                        }
                      />
                    </label>
                  );
                })}
              </div>
            </fieldset>
            <button
              className="primary enter-agent"
              disabled={enter.isPending}
              onClick={() => enter.mutate({ agent, tools: enabled })}
            >
              {enter.isPending ? (
                <>
                  <LoaderCircle className="spin" size={18} /> Saving permissions…
                </>
              ) : (
                <>
                  Enter agent <ArrowRight size={18} />
                </>
              )}
            </button>
            {enter.isError && <ErrorNotice error={enter.error} />}
          </article>
          <button
            className="agent-arrow next"
            aria-label="Next agent"
            onClick={() => switchAgent(1)}
            disabled={agents.length < 2 || enter.isPending}
          >
            <ChevronRight size={25} />
          </button>
        </section>
      ) : (
        <div className="home-empty">
          <Empty icon={<Sparkles />} title="Create your first agent">
            Choose the tools it can use, then start a chat.
          </Empty>
          <button className="primary" onClick={() => setCreating(true)}>
            <Plus size={17} /> Create agent
          </button>
        </div>
      )}
      {creating && (
        <AgentEditor
          onClose={() => setCreating(false)}
          onCreated={(agent) => {
            selectAgent(agent.id);
            navigate(`/chat/${agent.id}`);
          }}
        />
      )}
    </div>
  );
}
function ChatRedirect() {
  const q = useAgents();
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorNotice error={q.error} retry={() => q.refetch()} />;
  let remembered: string | null = null;
  try {
    remembered = localStorage.getItem('concierge-selected-agent-v1');
  } catch {
    /* Default to the first agent. */
  }
  const selected = q.data?.find((agent) => agent.id === remembered) || q.data?.[0];
  return selected ? (
    <Navigate to={`/chat/${selected.id}`} replace />
  ) : (
    <div className="page">
      <Empty icon={<MessageSquare />} title="Your first conversation starts here">
        Create an agent to get started.
      </Empty>
      <Link className="primary" to="/">
        Meet your agents <ArrowRight size={16} />
      </Link>
    </div>
  );
}
function ChatPage() {
  const { agentId = '' } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const action = params.get('action');
  const agents = useAgents();
  const agent = agents.data?.find((a) => a.id === agentId);
  const tasks = useTasks(agentId);
  const client = useQueryClient();
  const [message, setMessage] = useState('');
  const composer = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const shortcut = shortcuts[action as keyof typeof shortcuts];
    if (shortcut && agent?.tools.includes(shortcut.tool)) {
      setMessage(shortcut.prompt);
      composer.current?.focus();
    } else setMessage('');
  }, [agentId, action, agent?.id]);
  const bottom = useRef<HTMLDivElement>(null);
  const send = useMutation({
    mutationFn: (text: string) => api.send(agentId, text),
    onSuccess: () => {
      setMessage('');
      client.invalidateQueries({ queryKey: ['tasks', agentId] });
      client.invalidateQueries({ queryKey: ['history'] });
    },
  });
  const list = tasks.data || [];
  const active = list.some((t) => !['done', 'failed'].includes(t.status));
  const latest = list.at(-1);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [list.length, latest?.status]);
  if (agents.isPending) return <Loading />;
  if (agents.isError) return <ErrorNotice error={agents.error} retry={() => agents.refetch()} />;
  if (!agent)
    return (
      <div className="page">
        <Empty icon={<MessageSquare />} title="Agent not found">
          Choose an agent to start a conversation.
        </Empty>
        <Link to="/" className="text-button">
          View agents <ArrowRight size={16} />
        </Link>
      </div>
    );
  function submit(e: FormEvent) {
    e.preventDefault();
    if (message.trim() && !active && !send.isPending) send.mutate(message.trim());
  }
  return (
    <div className="chat-page">
      {/* Just the agent switcher: no name/status/tools block and no divider line. */}
      <div className="chat-top">
        <select
          aria-label="Choose agent"
          value={agentId}
          onChange={(e) => {
            navigate(`/chat/${e.target.value}`);
          }}
        >
          {agents.data?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>
      <div className="chat-layout">
        <section className="conversation" aria-label="Conversation">
          <div className="conversation-scroll">
            {!list.length && !tasks.isPending && (
              <div className="chat-welcome">
                <h1>What can I help with?</h1>
              </div>
            )}
            {tasks.isPending && <Loading />}
            {tasks.isError && <ErrorNotice error={tasks.error} retry={() => tasks.refetch()} />}
            {list.map((task) => (
              <div className="task-thread" key={task.id}>
                <div className="user-message">
                  <span>{task.goal}</span>
                  <span className="user-avatar">Y</span>
                </div>
                <div className="assistant-message">
                  <Avatar agent={agent} small />
                  <div className="assistant-body">
                    <strong>
                      {agent.name} <small>{dateTime(task.created_at)}</small>
                      <Link
                        className="task-history-link"
                        to={`/history/${encodeURIComponent(task.id)}`}
                      >
                        View task
                      </Link>
                    </strong>
                    <TaskCard task={task} agent={agent} />
                  </div>
                </div>
              </div>
            ))}
            <div ref={bottom} />
          </div>
          <form className="composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="message">
              Message {agent.name}
            </label>
            <textarea
              id="message"
              ref={composer}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submit(e);
                }
              }}
              placeholder={`Message ${agent.name}…`}
              rows={2}
              maxLength={4000}
              disabled={active || send.isPending}
            />
            <div className="composer-bottom">
              {/* Only says something when it matters: why the box is locked. */}
              <span>
                {active && (
                  <>
                    <Sparkles size={13} /> Task in progress
                  </>
                )}
              </span>
              <button
                className="send-button"
                aria-label="Send message"
                disabled={!message.trim() || active || send.isPending}
              >
                {send.isPending ? (
                  <LoaderCircle size={18} className="spin" />
                ) : (
                  <>
                    <span>Send</span>
                    <ArrowUp size={18} />
                  </>
                )}
              </button>
            </div>
            {send.isError && <ErrorNotice error={send.error} />}
          </form>
          <div className="composer-note">
            <ShieldCheck size={12} />
            {DEMO
              ? 'Demo mode. No real calls, emails, or charges.'
              : 'Payments always need your approval.'}
          </div>
        </section>
      </div>
    </div>
  );
}
function PaymentsPage() {
  const workspace = useWorkspaceTasks();
  const payments = workspace.tasks
    .filter((task) => task.payment)
    .sort(
      (a, b) =>
        Number(b.payment!.status === 'pending_approval') -
          Number(a.payment!.status === 'pending_approval') ||
        Date.parse(b.created_at) - Date.parse(a.created_at),
    );
  return (
    <div className="page">
      <PageHeading title="Payments" description="Review deposits before your agent pays." />
      {workspace.isPending ? (
        <Loading />
      ) : workspace.error ? (
        <ErrorNotice error={workspace.error} retry={workspace.retry} />
      ) : payments.length ? (
        <div className="payments-list">
          {payments.map((task) => (
            <article className="payment-entry" key={task.id}>
              <PaymentCard payment={task.payment!} agentId={task.agent_id} />
              <Link className="payment-task-link" to={`/chat/${task.agent_id}`}>
                View conversation <ArrowRight size={16} />
              </Link>
            </article>
          ))}
        </div>
      ) : (
        <Empty icon={<CreditCard size={28} />} title="No payments to review">
          When an agent requests a deposit, approve or decline it here.
        </Empty>
      )}
    </div>
  );
}
function AnalyticsPage() {
  const query = useQuery({
    queryKey: ['analytics'],
    queryFn: api.analytics,
    refetchInterval: 5000,
  });
  return (
    <div className="page">
      <PageHeading title="Activity" description="Calls and outcomes at a glance." />
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => query.refetch()} />
      ) : (
        query.data && (
          <>
            <div className="stat-grid">
              {[
                { label: 'Calls handled', value: query.data.total_calls, icon: Phone },
                {
                  label: 'Successful outcomes',
                  value: `${Math.round(query.data.success_rate)}%`,
                  icon: CheckCheck,
                },
                {
                  label: 'Average call length',
                  value: `${Math.round(query.data.avg_duration_seconds)}s`,
                  icon: Clock3,
                },
              ].map((stat) => (
                <div className="stat-card" key={stat.label}>
                  <span>
                    <stat.icon size={18} />
                  </span>
                  <p>{stat.label}</p>
                  <strong>{stat.value}</strong>
                  <small>{DEMO ? 'From your demo activity' : 'From your agent activity'}</small>
                </div>
              ))}
            </div>
            <div className="analytics-grid">
              <section className="chart-card">
                <div className="section-heading">
                  <h2>Calls through the week</h2>
                  <span>Last 7 days</span>
                </div>
                <div
                  className="bar-chart"
                  role="img"
                  aria-label={`Calls over the last seven days: ${query.data.calls_by_day.map((d) => `${d.date}: ${d.calls}`).join(', ')}`}
                >
                  {query.data.calls_by_day.map((day) => (
                    <div className="chart-column" key={day.date}>
                      <span>{day.calls}</span>
                      <div className="bar-track">
                        <div
                          className="bar"
                          style={{
                            height: `${(day.calls / Math.max(1, ...query.data!.calls_by_day.map((d) => d.calls))) * 100}%`,
                          }}
                        />
                      </div>
                      <small>
                        {new Date(`${day.date}T12:00:00`).toLocaleDateString('en-GB', {
                          weekday: 'short',
                        })}
                      </small>
                    </div>
                  ))}
                </div>
              </section>
              <section className="chart-card">
                <div className="section-heading">
                  <h2>Your team at a glance</h2>
                </div>
                {query.data.agents.map((agent) => (
                  <div className="agent-stat" key={agent.name}>
                    <span className="user-avatar">{agent.name.charAt(0)}</span>
                    <div>
                      <strong>{agent.name}</strong>
                      <small>{agent.calls} calls handled</small>
                    </div>
                    <b>
                      {Math.round(agent.success_rate)}%<small>success</small>
                    </b>
                  </div>
                ))}
              </section>
            </div>
            {!query.data.total_calls && (
              <div className="info-box">
                Your story starts with a task.{' '}
                <Link to="/chat">
                  Ask your agent to make a call <ArrowRight size={14} />
                </Link>
              </div>
            )}
            <p className="demo-note">
              {DEMO
                ? 'Live totals from simulated activity in this browser.'
                : 'Powered by Tiger Data call events and continuous aggregates.'}{' '}
              Success rate is measured across finished calls.
            </p>
          </>
        )
      )}
    </div>
  );
}
