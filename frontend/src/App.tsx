import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useParams,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUp,
  BarChart3,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  CreditCard,
  ExternalLink,
  LayoutGrid,
  LoaderCircle,
  Mail,
  MessageSquare,
  Phone,
  Plus,
  Radio,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { api, BASE, DEMO, downloadCalendar } from './api';
import type { Agent, AgentInput, CallEvent, CalendarEvent, Payment, Task, Tool } from './types';
const tools = {
  phone: { label: 'Phone calls', icon: Phone, description: 'Make calls on your behalf' },
  email: { label: 'Email', icon: Mail, description: 'Send confirmation emails' },
  calendar: { label: 'Calendar', icon: CalendarDays, description: 'Keep your plans in one place' },
  payments: {
    label: 'Payments',
    icon: CreditCard,
    description: 'Test payments, with your approval',
  },
};
const shortcuts = {
  call: {
    label: 'Make a call',
    icon: Phone,
    tool: 'phone' as Tool,
    prompt: 'Book a table for 4 at The Ivy Oxford tomorrow at 6pm. They may ask for a £20 deposit.',
  },
  email: {
    label: 'Send an email',
    icon: Mail,
    tool: 'email' as Tool,
    prompt: 'Draft and send an email. Ask me for the recipient and message before sending.',
  },
  calendar: {
    label: 'Plan my day',
    icon: CalendarDays,
    tool: 'calendar' as Tool,
    prompt: 'Help me organise my schedule for tomorrow.',
  },
};
const dateTime = (date: string) =>
  new Date(date).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
const money = (amount: number, currency: string) =>
  new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount / 100);
const labels = {
  planning: 'Thinking it through',
  calling: 'On the call',
  awaiting_approval: 'Needs your approval',
  done: 'Completed',
  failed: 'Needs attention',
};
function Avatar({ agent, small = false }: { agent?: Agent; small?: boolean }) {
  return (
    <span className={`avatar ${agent?.id === 'leo' ? 'lavender' : ''} ${small ? 'small' : ''}`}>
      {agent?.name.charAt(0).toUpperCase() || 'C'}
      <span />
    </span>
  );
}
function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="error-notice">
      <span>
        {error instanceof Error ? error.message : 'Something went wrong. Please try again.'}
      </span>
      {retry && (
        <button className="text-button" onClick={retry}>
          Try again <ArrowRight size={14} />
        </button>
      )}
    </div>
  );
}
function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={22} /> Getting everything ready…
    </div>
  );
}
function Empty({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon">{icon}</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function useAgents() {
  return useQuery({ queryKey: ['agents'], queryFn: api.agents });
}
function useTasks(agentId: string) {
  return useQuery({
    queryKey: ['tasks', agentId],
    queryFn: () => api.tasks(agentId),
    enabled: !!agentId,
    refetchInterval: 1200,
    refetchIntervalInBackground: true,
  });
}
function useWorkspaceTasks() {
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
export default function App() {
  const { data: agents = [] } = useAgents();
  const [help, setHelp] = useState(false);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <Sparkles size={22} />
          </span>
          concierge<span className="brand-dot">.</span>
        </Link>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          <NavLink to="/agents">
            <LayoutGrid size={19} /> Agents <span className="nav-count">{agents.length}</span>
          </NavLink>
          <NavLink to="/chat">
            <MessageSquare size={19} /> Chat
          </NavLink>
          <NavLink to="/calendar">
            <CalendarDays size={19} /> Calendar
          </NavLink>
          <NavLink to="/payments">
            <CreditCard size={19} /> Payments
          </NavLink>
          <NavLink to="/analytics" className="secondary-nav">
            <BarChart3 size={19} /> Analytics
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={18} /> Help <ExternalLink size={13} />
          </button>
          <div className="profile">
            <span className="user-avatar">Y</span>
            <div>
              <strong>Your workspace</strong>
              <small>Personal account</small>
            </div>
            <span className="online-dot" />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>Personal workspace</span>
          <div className="workspace-options">
            <Link className="mobile-activity" to="/analytics" aria-label="Analytics">
              <BarChart3 size={17} />
            </Link>
            <span className="mode-badge">
              <span /> {DEMO ? 'Demo · simulated' : 'Connected to backend'}
            </span>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Navigate to="/agents" replace />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/chat" element={<ChatRedirect />} />
            <Route path="/chat/:agentId" element={<ChatPage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/payments" element={<PaymentsPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="*" element={<Navigate to="/agents" replace />} />
          </Routes>
        </main>
      </div>
      {help && (
        <Modal title="Meet your concierge" onClose={() => setHelp(false)}>
          <p className="modal-copy">
            Create an agent, choose its tools, and give it a task in chat. You can watch calls
            unfold, approve deposits, and find confirmed plans in your calendar.
          </p>
          <div className="info-box">
            {DEMO
              ? 'This is a local demo. Calls, emails, reservations, and payments are simulated. Try the suggested dinner booking to see the full flow. Type “no answer” to try a failed call.'
              : 'Tasks are sent to your connected backend. Payments require your approval.'}
          </div>
          <button className="primary full" onClick={() => setHelp(false)}>
            Got it <Check size={16} />
          </button>
        </Modal>
      )}
    </div>
  );
}
function PageHeading({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
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
        title="Choose your agent"
        description="Set its permissions, then start a chat."
        action={
          <button className="secondary create-agent-button" onClick={() => setCreating(true)}>
            <Plus size={17} /> <span>Create agent</span>
          </button>
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
            <div className="selected-agent-identity">
              <Avatar agent={agent} />
              <h2>{agent.name}</h2>
              <span className="agent-role">
                {agent.tools.includes('phone') ? 'Everyday concierge' : 'Personal assistant'}
              </span>
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
            <p className="permissions-note">
              <ShieldCheck size={14} /> Payments always ask for approval.
            </p>
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
            <details className="agent-details">
              <summary>Agent instructions</summary>
              <p>{agent.persona}</p>
            </details>
          </article>
          <button
            className="agent-arrow next"
            aria-label="Next agent"
            onClick={() => switchAgent(1)}
            disabled={agents.length < 2 || enter.isPending}
          >
            <ChevronRight size={25} />
          </button>
          <p className="agent-position" aria-live="polite">
            Agent {index + 1} of {agents.length}
          </p>
        </section>
      ) : (
        <Empty icon={<Sparkles />} title="Create your first agent">
          Choose the tools it can use, then start a chat.
        </Empty>
      )}
      {creating && (
        <AgentModal
          onClose={() => setCreating(false)}
          onCreated={(agent) => selectAgent(agent.id)}
        />
      )}
    </div>
  );
}
function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="modal-header">
        <h2>{title}</h2>
        <button className="icon-button" aria-label="Close dialog" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function AgentModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated?: (agent: Agent) => void;
}) {
  const client = useQueryClient();
  const [enabled, setEnabled] = useState<Tool[]>(['phone', 'email', 'calendar', 'payments']);
  const mutation = useMutation({
    mutationFn: api.createAgent,
    onSuccess: (agent) => {
      client.invalidateQueries({ queryKey: ['agents'] });
      onCreated?.(agent);
      onClose();
    },
  });
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const input: AgentInput = {
      name: String(data.get('name')).trim(),
      persona: String(data.get('persona')).trim(),
      voice: String(data.get('voice')),
      tools: enabled,
    };
    if (input.name && input.persona) mutation.mutate(input);
  }
  return (
    <Modal title="Create an agent" onClose={onClose}>
      <form onSubmit={submit}>
        <label>
          Agent name
          <input name="name" placeholder="e.g. Maya" required maxLength={40} autoFocus />
        </label>
        <label>
          Personality & instructions
          <textarea
            name="persona"
            placeholder="A thoughtful concierge who handles bookings and everyday errands…"
            required
            maxLength={1500}
            rows={3}
          />
        </label>
        <label>
          Voice
          <select name="voice">
            <option>Warm & natural</option>
            <option>Calm & clear</option>
            <option>Bright & friendly</option>
          </select>
        </label>
        <fieldset>
          <legend>Tools</legend>
          <div className="tool-options">
            {Object.entries(tools).map(([key, tool]) => {
              const Icon = tool.icon;
              return (
                <label
                  key={key}
                  className={`tool-option ${enabled.includes(key as Tool) ? 'selected' : ''}`}
                >
                  <Icon size={19} />
                  <span>
                    <strong>{tool.label}</strong>
                    <small>{tool.description}</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={enabled.includes(key as Tool)}
                    onChange={(e) =>
                      setEnabled(
                        e.target.checked
                          ? [...enabled, key as Tool]
                          : enabled.filter((t) => t !== key),
                      )
                    }
                  />
                </label>
              );
            })}
          </div>
        </fieldset>
        {mutation.isError && <ErrorNotice error={mutation.error} />}
        <button className="primary full" disabled={mutation.isPending}>
          {mutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}{' '}
          Create agent
        </button>
      </form>
    </Modal>
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
      <Link className="primary" to="/agents">
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
        <Link to="/agents" className="text-button">
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
      <div className="chat-top">
        <div className="chat-identity">
          <Avatar agent={agent} small />
          <div>
            <h2>
              {agent.name}{' '}
              <span className="available">
                <span /> Ready to help
              </span>
            </h2>
            <p>{agent.tools.map((tool) => tools[tool]?.label || tool).join(' · ')}</p>
          </div>
        </div>
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
                <div className="suggestions">
                  {Object.entries(shortcuts)
                    .filter(([, shortcut]) => agent.tools.includes(shortcut.tool))
                    .map(([key, shortcut]) => {
                      const Icon = shortcut.icon;
                      return (
                        <button
                          key={key}
                          onClick={() => {
                            setMessage(shortcut.prompt);
                            composer.current?.focus();
                          }}
                        >
                          <Icon size={18} />
                          <span>{key === 'call' ? 'Book a table' : shortcut.label}</span>
                          <ArrowRight size={16} />
                        </button>
                      );
                    })}
                </div>
                {DEMO && <p className="demo-note">Try “Book a table” for the simulated booking.</p>}
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
              <span>
                <Sparkles size={13} />
                {active ? 'Task in progress' : 'Enter to send · Shift + Enter for a new line'}
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
function useCallEvents(task: Task) {
  const [events, setEvents] = useState<CallEvent[]>([]);
  const [reconnecting, setReconnecting] = useState(false);
  const callId = task.call?.id;
  const terminal = task.status === 'done' || task.status === 'failed';
  useEffect(() => {
    setEvents([]);
    setReconnecting(false);
    if (DEMO || !callId || terminal) return;
    const stream = new EventSource(`${BASE}/calls/${encodeURIComponent(callId)}/events/stream`);
    const receive = (message: MessageEvent) => {
      try {
        const event: CallEvent = JSON.parse(message.data);
        if (!event.kind || !event.ts || event.call_id !== callId) return;
        setEvents((old) =>
          old.some(
            (e) =>
              e.ts === event.ts &&
              e.kind === event.kind &&
              JSON.stringify(e.payload) === JSON.stringify(event.payload),
          )
            ? old
            : [...old, event],
        );
        setReconnecting(false);
      } catch {
        /* Ignore incomplete or heartbeat frames. */
      }
    };
    stream.onmessage = receive;
    for (const kind of [
      'dialing',
      'ringing',
      'answered',
      'transcript_line',
      'tool_call',
      'payment',
      'ended',
    ])
      stream.addEventListener(kind, receive as EventListener);
    stream.onopen = () => setReconnecting(false);
    stream.onerror = () => setReconnecting(true);
    return () => stream.close();
  }, [callId, terminal]);
  const combined = [...(task.events || [])];
  for (const e of events)
    if (
      !combined.some(
        (x) =>
          x.ts === e.ts &&
          x.kind === e.kind &&
          JSON.stringify(x.payload) === JSON.stringify(e.payload),
      )
    )
      combined.push(e);
  return { events: combined.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts)), reconnecting };
}
function TaskCard({ task, agent }: { task: Task; agent: Agent }) {
  const { events, reconnecting } = useCallEvents(task);
  const [now, setNow] = useState(Date.now());
  const running = !['done', 'failed'].includes(task.status);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  const duration = task.call
    ? Math.max(
        0,
        Math.floor(
          ((task.call.ended_at ? Date.parse(task.call.ended_at) : now) -
            Date.parse(task.call.started_at)) /
            1000,
        ),
      )
    : 0;
  const streamed = events
    .filter((e) => e.kind === 'transcript_line')
    .map((e) => ({ speaker: e.payload.speaker || agent.name, text: e.payload.text || '' }));
  const transcript = streamed.length ? streamed : task.call?.transcript || [];
  return (
    <div className={`task-card ${task.status === 'failed' ? 'failed' : ''}`}>
      <div className="task-card-header">
        <span className="call-icon">
          {task.call ? <Phone size={17} /> : <Sparkles size={17} />}
        </span>
        <div>
          <strong>{task.call ? 'Phone call' : 'Task'}</strong>
          <small>
            {task.call
              ? `${DEMO ? 'Simulated call' : 'Phone call'} · ${String(Math.floor(duration / 60)).padStart(2, '0')}:${String(duration % 60).padStart(2, '0')}`
              : agent.name}
          </small>
        </div>
        <span className={`status-chip ${task.status}`}>
          {running && <span className="pulse-dot" />}
          {task.status === 'done' && <Check size={12} />}
          {labels[task.status]}
        </span>
      </div>
      {task.summary && (
        <div className={`summary ${task.status === 'failed' ? 'summary-error' : ''}`}>
          <span>
            {task.status === 'failed' ? <CircleHelp size={18} /> : <CheckCheck size={18} />}
          </span>
          <div>
            <strong>
              {task.status === 'failed'
                ? 'Let’s try another way'
                : task.payment?.status === 'denied'
                  ? 'Your decision, respected.'
                  : 'All taken care of.'}
            </strong>
            <p>{task.summary}</p>
            {task.status === 'failed' && <small>Send a new message below to try again.</small>}
          </div>
        </div>
      )}
      {task.payment && <PaymentCard payment={task.payment} agentId={task.agent_id} />}
      {task.call && (
        <details className="call-details" open={running}>
          <summary>
            <Radio size={15} />
            <strong>{running ? 'Live transcript' : 'Call transcript'}</strong>
            {DEMO && <span>Simulated</span>}
          </summary>
          <div className="event-timeline">
            {events
              .filter((e) => e.kind !== 'transcript_line')
              .map((e, i) => (
                <span key={`${e.ts}-${i}`} title={e.payload.text}>
                  <i />
                  {e.kind === 'payment'
                    ? 'Approval'
                    : e.kind === 'ended'
                      ? 'Finished'
                      : e.kind.charAt(0).toUpperCase() + e.kind.slice(1)}
                </span>
              ))}
          </div>
          <div className="transcript">
            {transcript.length ? (
              transcript.map((line, i) => (
                <div
                  className={`transcript-line ${line.speaker === agent.name ? 'agent-line' : ''}`}
                  key={i}
                >
                  <span>{line.speaker}</span>
                  <p>{line.text}</p>
                </div>
              ))
            ) : (
              <p className="muted">Waiting for the call to connect…</p>
            )}
            {reconnecting && (
              <p className="muted" role="status">
                Reconnecting to the live stream. Checking task updates in the meantime.
              </p>
            )}
          </div>
        </details>
      )}
      {task.calendar_event && (
        <Link className="calendar-result" to="/calendar">
          <CalendarDays size={20} />
          <div>
            <strong>{task.calendar_event.title}</strong>
            <small>{dateTime(task.calendar_event.starts_at)}</small>
          </div>
          <ArrowRight size={16} />
        </Link>
      )}
    </div>
  );
}
function PaymentCard({ payment, agentId }: { payment: Payment; agentId: string }) {
  const client = useQueryClient();
  const decision = useMutation({
    mutationFn: (approve: boolean) => api.decide(payment.id, approve),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['tasks', agentId] });
      client.invalidateQueries({ queryKey: ['calendar'] });
      client.invalidateQueries({ queryKey: ['analytics'] });
    },
  });
  return (
    <div className={`payment-card ${payment.status === 'pending_approval' ? 'pending' : ''}`}>
      <div className="payment-title">
        <span className="payment-icon">
          <CreditCard size={21} />
        </span>
        <div>
          <strong>
            {payment.status === 'pending_approval'
              ? 'Approve deposit'
              : payment.status === 'denied'
                ? 'Payment declined'
                : 'Payment approved'}
          </strong>
          <small>{payment.merchant || 'Booking deposit'}</small>
        </div>
        <b>{money(payment.amount, payment.currency)}</b>
      </div>
      {payment.status === 'pending_approval' && (
        <div className="payment-actions">
          <button
            className="primary"
            onClick={() => decision.mutate(true)}
            disabled={decision.isPending}
          >
            <Check size={17} /> Approve {money(payment.amount, payment.currency)}
          </button>
          <button
            className="secondary"
            onClick={() => decision.mutate(false)}
            disabled={decision.isPending}
          >
            Decline
          </button>
        </div>
      )}
      <small className="payment-disclaimer">
        <ShieldCheck size={13} /> Test payment · No real charge
      </small>
      {decision.isError && <ErrorNotice error={decision.error} />}
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
function CalendarPage() {
  const query = useQuery({ queryKey: ['calendar'], queryFn: api.calendar, refetchInterval: 5000 });
  const [month, setMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const [view, setView] = useState<'list' | 'month'>('list');
  const events = query.data || [];
  const sorted = [...events].sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at));
  const monthEvents = sorted.filter(
    (e) =>
      new Date(e.starts_at).getMonth() === month.getMonth() &&
      new Date(e.starts_at).getFullYear() === month.getFullYear(),
  );
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const offset = (month.getDay() + 6) % 7;
  return (
    <div className="page">
      <PageHeading
        title="Calendar"
        description="Your confirmed plans."
        action={
          <button
            className="secondary"
            disabled={!events.length}
            onClick={() => downloadCalendar(events)}
          >
            <ArrowDownToLine size={16} /> Export calendar
          </button>
        }
      />
      <div className="section-heading">
        <h2>
          Your calendar <span>{events.length}</span>
        </h2>
        <div className="segmented">
          <button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>
            List
          </button>
          <button className={view === 'month' ? 'active' : ''} onClick={() => setView('month')}>
            Month
          </button>
        </div>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => query.refetch()} />
      ) : view === 'list' ? (
        <div className="calendar-list">
          {sorted.length ? (
            sorted.map((event) => <CalendarRow key={event.id} event={event} />)
          ) : (
            <Empty icon={<CalendarDays size={28} />} title="No plans yet">
              Ask an agent to make a booking.
            </Empty>
          )}
        </div>
      ) : (
        <div className="month-calendar">
          <div className="month-header">
            <h2>{month.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })}</h2>
            <div>
              <button
                className="icon-button"
                aria-label="Previous month"
                onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
              >
                <ChevronLeft size={18} />
              </button>
              <button
                className="icon-button"
                aria-label="Next month"
                onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
          <div className="month-grid">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
              <div className="day-heading" key={d}>
                {d}
              </div>
            ))}
            {Array.from({ length: offset }, (_, i) => (
              <div className="day-cell blank" key={`blank-${i}`} />
            ))}
            {Array.from({ length: days }, (_, i) => (
              <div
                className={`day-cell ${new Date().toDateString() === new Date(month.getFullYear(), month.getMonth(), i + 1).toDateString() ? 'today' : ''}`}
                key={i}
              >
                <span>{i + 1}</span>
                {monthEvents
                  .filter((e) => new Date(e.starts_at).getDate() === i + 1)
                  .map((e) => (
                    <span
                      className="month-event"
                      key={e.id}
                      title={`${e.title} · ${dateTime(e.starts_at)}`}
                    >
                      {e.title}
                    </span>
                  ))}
              </div>
            ))}
          </div>
        </div>
      )}
      <p className="demo-note">Export to Apple Calendar, Google Calendar, or Outlook.</p>
    </div>
  );
}
function CalendarRow({ event }: { event: CalendarEvent }) {
  const date = new Date(event.starts_at);
  return (
    <article className="calendar-row">
      <div className="date-tile">
        <span>{date.toLocaleDateString('en-GB', { month: 'short' })}</span>
        <b>{date.getDate()}</b>
      </div>
      <div>
        <span className="eyebrow">CONFIRMED PLAN</span>
        <h3>{event.title}</h3>
        <p>
          <Clock3 size={13} />
          {date.toLocaleDateString('en-GB', { weekday: 'long' })} ·{' '}
          {date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} –{' '}
          {new Date(event.ends_at).toLocaleTimeString('en-GB', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
        <small>{event.location}</small>
      </div>
      <span className="status-chip done">
        <Check size={12} /> Confirmed
      </span>
    </article>
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
