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
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  MessageSquare,
  Plus,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { api, DEMO } from './api';
import { tools, shortcuts, dateTime } from './config';
import { Avatar, ErrorNotice, Loading, Empty, PageHeading } from './components/ui';
import { TaskCard } from './components/TaskCard';
import { useAgents, useTasks } from './state';
import { AgentEditor } from './features/agents/AgentEditor';
import type { Agent, Tool } from './types';
import { AgentActions } from './features/agents/AgentActions';
export default function App() {
  // No sidebar: the logo is the one way home, the home page is the agents page, and chats are
  // entered from there.
  return (
    <div className="app-shell">
      <div className="main-shell">
        <header className="topbar">
          <Link to="/" className="brand brand-button" aria-label="Smart Connect home">
            <span className="brand-mark">
              <Sparkles size={20} />
            </span>
            Smart Connect
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
      {/* Just a way back to the agents: no name/status/tools block and no divider line. */}
      <div className="chat-top">
        <Link to="/" className="text-button">
          <ChevronLeft size={18} /> Agents
        </Link>
      </div>
      <div className="chat-layout">
        <section className="conversation" aria-label="Conversation">
          <div className="conversation-scroll">
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
          {DEMO && (
            <div className="composer-note">
              <ShieldCheck size={12} /> Demo mode. No real calls, emails, or charges.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
