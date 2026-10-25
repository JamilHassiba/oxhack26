import type { Agent, AgentInput, Analytics, CalendarEvent, Task, Tool } from './types';
import type { HistoryEntry, TaskHistory } from './history-types';
import { isActive, previousAgent } from './history-types';
import { isDemoScenario, scenarioFor, type DemoScenario } from './features/demo/scenarios';
const key = 'concierge-demo-v1';
const presets: Agent[] = [
  {
    id: 'maya',
    name: 'Maya',
    voice: 'Warm & natural',
    tools: ['phone', 'email', 'calendar', 'payments'],
  },
  {
    id: 'leo',
    name: 'Leo',
    voice: 'Calm & clear',
    tools: ['email', 'calendar'],
  },
];
type Run = { scenario: DemoScenario; agent: Agent };
type State = { agents: Agent[]; tasks: Task[]; runs: Record<string, Run> };
let memory: State | undefined;
let persistent = true;
function state(): State {
  if (memory) return memory;
  try {
    const saved = JSON.parse(localStorage.getItem(key) || 'null');
    if (Array.isArray(saved?.agents) && Array.isArray(saved?.tasks)) {
      // Add run metadata lazily so existing MVP demos survive this upgrade.
      return (memory = {
        agents: saved.agents,
        tasks: saved.tasks,
        runs: saved.runs && typeof saved.runs === 'object' ? saved.runs : {},
      });
    }
  } catch {
    persistent = false;
  }
  return (memory = { agents: structuredClone(presets), tasks: [], runs: {} });
}
function save() {
  try {
    localStorage.setItem(key, JSON.stringify(state()));
    persistent = true;
  } catch {
    persistent = false;
  }
}
function run(task: Task): Run {
  return (state().runs[task.id] ||= {
    scenario: scenarioFor(task.goal),
    agent: structuredClone(
      state().agents.find((a) => a.id === task.agent_id) || previousAgent(task.agent_id),
    ),
  });
}
function at(task: Task, elapsed: number) {
  return new Date(Date.parse(task.created_at) + elapsed).toISOString();
}
function addEvent(
  task: Task,
  kind: Task['events'][number]['kind'],
  text: string,
  speaker?: string,
  ts = new Date().toISOString(),
) {
  task.events.push({ ts, call_id: task.call!.id, kind, payload: { text, speaker } });
  if (kind === 'transcript_line') task.call!.transcript.push({ speaker: speaker!, text });
}
function endCall(task: Task, ts: string) {
  if (!task.call || task.call.ended_at) return;
  task.call.status = 'ended';
  task.call.ended_at = ts;
  addEvent(task, 'ended', 'Call finished', undefined, ts);
}
function fail(task: Task, summary: string, elapsed = 6000) {
  task.status = 'failed';
  task.summary = summary;
  endCall(task, at(task, elapsed));
}
function complete(task: Task, ts = new Date().toISOString()) {
  const { agent, scenario } = run(task);
  const hour = scenario === 'alternative_time' ? 19 : 18;
  const denied = task.payment?.status === 'denied';
  task.status = 'done';
  endCall(task, ts);
  if (task.payment?.status === 'approved') task.payment.status = 'paid';
  task.summary = denied
    ? 'Deposit declined. No payment or reservation was made.'
    : task.call
      ? `Table for 4 confirmed at The Ivy Oxford tomorrow at ${hour}:00.${task.payment ? ' £20 test deposit approved.' : ''}${agent.tools.includes('email') ? ' Demo confirmation email prepared.' : ''}`
      : 'Demo request completed.';
  if (!denied && agent.tools.includes('calendar')) {
    const starts = new Date(task.created_at);
    starts.setDate(starts.getDate() + 1);
    starts.setHours(hour, 0, 0, 0);
    task.calendar_event = {
      id: `event-${task.id}`,
      task_id: task.id,
      title: task.call ? 'Dinner at The Ivy Oxford · 4 guests' : task.goal,
      starts_at: starts.toISOString(),
      ends_at: new Date(+starts + 90 * 60000).toISOString(),
      location: task.call ? 'The Ivy Oxford, 120–121 High Street, Oxford' : '',
    };
  }
}
function advance(task: Task) {
  if (!isActive(task) || task.status === 'awaiting_approval') return task;
  const { agent, scenario } = run(task);
  const age = Date.now() - Date.parse(task.created_at);
  if (task.status === 'planning' && age >= 900) {
    if (!agent.tools.includes('phone')) {
      complete(task, at(task, 900));
      return task;
    }
    task.status = 'calling';
    task.call = {
      id: `call-${task.id}`,
      status: 'dialing',
      started_at: at(task, 900),
      transcript: [],
    };
    addEvent(task, 'dialing', 'Calling The Ivy Oxford', undefined, at(task, 900));
  }
  if (task.status !== 'calling') return task;
  if (age >= 1800 && !task.events.some((e) => e.kind === 'ringing'))
    addEvent(task, 'ringing', 'Phone ringing', undefined, at(task, 1800));
  if (scenario === 'no_answer') {
    if (age >= 6000)
      fail(task, 'The restaurant did not answer. Try again or choose another restaurant.');
    return task;
  }
  if (age >= 2500 && !task.events.some((e) => e.kind === 'answered')) {
    task.call!.status = 'answered';
    addEvent(task, 'answered', 'Connected to the restaurant', undefined, at(task, 2500));
    addEvent(
      task,
      'transcript_line',
      `Hi, I’m ${agent.name}, an AI assistant calling on behalf of my user. Could I book a table for four tomorrow at six?`,
      agent.name,
      at(task, 2600),
    );
  }
  if (age >= 4500 && task.call!.transcript.length === 1) {
    const text =
      scenario === 'fully_booked'
        ? 'I’m sorry, we’re fully booked all evening. There are no alternative times available.'
        : scenario === 'alternative_time'
          ? 'Six is full, but we can offer seven. No deposit is needed.'
          : 'Of course. We have a table at six. There’s a £20 deposit to secure the booking.';
    addEvent(task, 'transcript_line', text, 'Restaurant', at(task, 4500));
  }
  if (age >= 6000) {
    if (scenario === 'fully_booked')
      fail(task, 'The restaurant is fully booked. No reservation or payment was made.');
    else if (scenario === 'alternative_time') {
      addEvent(
        task,
        'transcript_line',
        'Seven works with the fallback my user approved. Please confirm the table for four.',
        agent.name,
        at(task, 5500),
      );
      complete(task, at(task, 6000));
    } else if (agent.tools.includes('payments')) {
      task.status = 'awaiting_approval';
      task.payment = {
        id: `payment-${task.id}`,
        task_id: task.id,
        amount: 2000,
        currency: 'GBP',
        merchant: 'The Ivy Oxford',
        status: 'pending_approval',
      };
      addEvent(task, 'payment', 'Waiting for your approval', undefined, at(task, 6000));
    } else fail(task, 'A deposit is required. Enable payments before starting another booking.');
  }
  return task;
}
function findTask(id: string) {
  const task = state().tasks.find((t) => t.id === id);
  if (!task) throw new Error('Task not found.');
  return task;
}
function validateAgent(input: AgentInput) {
  if (!input.name.trim() || input.name.trim().length > 40)
    throw new Error('Enter a name of up to 40 characters.');
  if (input.tools.some((t) => !['phone', 'email', 'calendar', 'payments'].includes(t)))
    throw new Error('Unknown tool permission.');
  return {
    ...input,
    name: input.name.trim(),
    tools: [...new Set(input.tools)],
  };
}
export const demo = {
  async agents() {
    return structuredClone(state().agents);
  },
  async createAgent(input: AgentInput) {
    const agent = { ...validateAgent(input), id: crypto.randomUUID() };
    state().agents.push(agent);
    save();
    return structuredClone(agent);
  },
  async updateAgent(id: string, input: Partial<AgentInput>) {
    const index = state().agents.findIndex((a) => a.id === id);
    if (index < 0) throw new Error('Agent not found.');
    state().agents[index] = { ...validateAgent({ ...state().agents[index], ...input }), id };
    save();
    return structuredClone(state().agents[index]);
  },
  async setAgentTools(id: string, tools: Tool[]) {
    return demo.updateAgent(id, { tools });
  },
  async deleteAgent(id: string) {
    if (!state().agents.some((a) => a.id === id)) throw new Error('Agent not found.');
    state().tasks.forEach((t) => {
      run(t);
      advance(t);
    });
    save();
    if (state().tasks.some((t) => t.agent_id === id && isActive(t)))
      throw new Error('Finish this agent’s active tasks and payment approvals before deleting it.');
    state().agents = state().agents.filter((a) => a.id !== id);
    save();
  },
  async tasks(agentId: string) {
    return structuredClone(
      state()
        .tasks.filter((t) => t.agent_id === agentId)
        .map(advance),
    );
  },
  async send(agentId: string, goal: string, scenario?: DemoScenario) {
    const agent = state().agents.find((a) => a.id === agentId);
    if (!agent) throw new Error('Agent not found.');
    if (!goal.trim()) throw new Error('Enter a request.');
    if (state().tasks.some((t) => t.agent_id === agentId && isActive(advance(t))))
      throw new Error('Finish the current task before starting another.');
    const selected = scenario ?? scenarioFor(goal);
    if (!isDemoScenario(selected)) throw new Error('Unknown demo scenario.');
    const task: Task = {
      id: crypto.randomUUID(),
      agent_id: agentId,
      goal: goal.trim(),
      status: 'planning',
      created_at: new Date().toISOString(),
      events: [],
    };
    state().runs[task.id] = { scenario: selected, agent: structuredClone(agent) };
    state().tasks.push(task);
    save();
    return { task_id: task.id };
  },
  async task(id: string) {
    const task = advance(findTask(id));
    save();
    return structuredClone(task);
  },
  async history(): Promise<TaskHistory> {
    const items = state().tasks.map((task) => ({
      task: structuredClone(advance(task)),
      agent: structuredClone(run(task).agent),
    }));
    save();
    return { items, unavailable: [], scope: 'demo', persistent };
  },
  async taskDetail(id: string): Promise<HistoryEntry> {
    const task = advance(findTask(id));
    save();
    return { task: structuredClone(task), agent: structuredClone(run(task).agent) };
  },
  async decide(id: string, approve: boolean) {
    const task = state().tasks.find((t) => t.payment?.id === id);
    if (!task?.payment || task.payment.status !== 'pending_approval')
      throw new Error('This payment has already been handled.');
    task.payment.status = approve ? 'approved' : 'denied';
    addEvent(
      task,
      'transcript_line',
      approve
        ? 'The test deposit is approved. Thank you for confirming the reservation.'
        : 'We won’t proceed with the deposit. Thank you for your time.',
      run(task).agent.name,
    );
    complete(task);
    save();
  },
  async calendar(): Promise<CalendarEvent[]> {
    state().tasks.forEach(advance);
    save();
    return structuredClone(
      state().tasks.flatMap((t) => (t.calendar_event ? [t.calendar_event] : [])),
    );
  },
  async analytics(): Promise<Analytics> {
    state().tasks.forEach(advance);
    save();
    const calls = state().tasks.filter((t) => t.call);
    const ended = calls.filter((t) => t.call?.ended_at);
    const successful = (task: Task) => task.status === 'done' && task.payment?.status !== 'denied';
    const roster = new Map(state().agents.map((a) => [a.id, a]));
    for (const task of state().tasks)
      if (!roster.has(task.agent_id)) roster.set(task.agent_id, run(task).agent);
    return {
      total_calls: calls.length,
      success_rate: ended.length ? (ended.filter(successful).length / ended.length) * 100 : 0,
      avg_duration_seconds: ended.length
        ? ended.reduce(
            (sum, t) =>
              sum + (Date.parse(t.call!.ended_at!) - Date.parse(t.call!.started_at)) / 1000,
            0,
          ) / ended.length
        : 0,
      calls_by_day: Array.from({ length: 7 }, (_, i) => {
        const d = new Date();
        d.setDate(d.getDate() - 6 + i);
        const date = d.toLocaleDateString('en-CA');
        return {
          date,
          calls: calls.filter((t) => new Date(t.created_at).toLocaleDateString('en-CA') === date)
            .length,
        };
      }),
      agents: [...roster.values()].map((a) => {
        const tasks = ended.filter((t) => t.agent_id === a.id);
        return {
          name: a.name,
          calls: calls.filter((t) => t.agent_id === a.id).length,
          success_rate: tasks.length ? (tasks.filter(successful).length / tasks.length) * 100 : 0,
        };
      }),
    };
  },
};
