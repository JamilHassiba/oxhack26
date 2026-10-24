import type { Agent, AgentInput, Analytics, CalendarEvent, Task } from './types';
const key = 'concierge-demo-v1';
const presets: Agent[] = [
  {
    id: 'maya',
    name: 'Maya',
    persona:
      'Your thoughtful everyday concierge. I take care of bookings, appointments, and the little details, so you can focus on your day.',
    voice: 'Warm & natural',
    tools: ['phone', 'email', 'calendar', 'payments'],
  },
  {
    id: 'leo',
    name: 'Leo',
    persona:
      'Your calm, organised work assistant. I coordinate your schedule and keep your inbox in order.',
    voice: 'Calm & clear',
    tools: ['email', 'calendar'],
  },
];
type State = { agents: Agent[]; tasks: Task[] };
let memory: State | undefined;
function state(): State {
  if (memory) return memory;
  try {
    const saved = JSON.parse(localStorage.getItem(key) || 'null');
    if (saved?.agents && saved?.tasks) return (memory = saved);
  } catch {
    /* Storage unavailable or an old fixture. */
  }
  return (memory = { agents: structuredClone(presets), tasks: [] });
}
function save() {
  try {
    localStorage.setItem(key, JSON.stringify(state()));
  } catch {
    /* In-memory demo still works. */
  }
}
function addEvent(
  task: Task,
  kind: Task['events'][number]['kind'],
  text: string,
  speaker?: string,
) {
  task.events.push({
    ts: new Date().toISOString(),
    call_id: task.call!.id,
    kind,
    payload: { text, speaker },
  });
  if (kind === 'transcript_line') task.call!.transcript.push({ speaker: speaker!, text });
}
function complete(task: Task) {
  const agent = state().agents.find((a) => a.id === task.agent_id)!;
  task.status = 'done';
  if (task.call) {
    task.call.status = 'ended';
    task.call.ended_at = new Date().toISOString();
    addEvent(task, 'ended', 'Call finished');
  }
  const denied = task.payment?.status === 'denied';
  if (task.payment?.status === 'approved') task.payment.status = 'paid';
  task.summary = denied
    ? 'You declined the deposit. No payment was made and no reservation was confirmed.'
    : `Demo task completed.${task.call ? ' A table for four is reserved at The Ivy Oxford at 6:00 pm tomorrow.' : ' Your request has been organised.'}${task.payment ? ' The £20 test deposit was approved.' : ''}${agent.tools.includes('email') ? ' A simulated confirmation email is ready.' : ''}`;
  if (!denied && agent.tools.includes('calendar')) {
    const starts = new Date();
    starts.setDate(starts.getDate() + 1);
    starts.setHours(18, 0, 0, 0);
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
export const demo = {
  async agents() {
    return structuredClone(state().agents);
  },
  async createAgent(input: AgentInput) {
    const agent = { ...input, id: crypto.randomUUID() };
    state().agents.push(agent);
    save();
    return agent;
  },
  async tasks(agentId: string) {
    return structuredClone(state().tasks.filter((t) => t.agent_id === agentId));
  },
  async send(agentId: string, goal: string) {
    const task: Task = {
      id: crypto.randomUUID(),
      agent_id: agentId,
      goal,
      status: 'planning',
      created_at: new Date().toISOString(),
      events: [],
    };
    state().tasks.push(task);
    save();
    return { task_id: task.id };
  },
  async task(id: string) {
    const task = state().tasks.find((t) => t.id === id);
    if (!task) throw new Error('Task not found.');
    const agent = state().agents.find((a) => a.id === task.agent_id)!;
    const age = Date.now() - Date.parse(task.created_at);
    if (task.status === 'planning' && age >= 900) {
      if (/\b(fail|no answer)\b/i.test(task.goal)) {
        task.status = 'failed';
        task.summary = 'The restaurant did not answer. Try again or ask for another restaurant.';
      } else if (!agent.tools.includes('phone')) complete(task);
      else {
        task.status = 'calling';
        task.call = {
          id: `call-${id}`,
          status: 'dialing',
          started_at: new Date().toISOString(),
          transcript: [],
        };
        addEvent(task, 'dialing', 'Calling The Ivy Oxford');
      }
    }
    if (task.status === 'calling') {
      if (age >= 2500 && !task.events.some((e) => e.kind === 'answered')) {
        task.call!.status = 'answered';
        addEvent(task, 'answered', 'Connected to the restaurant');
        addEvent(
          task,
          'transcript_line',
          `Hi, I’m ${agent.name}, an AI assistant calling on behalf of my user. Could I book a table for four tomorrow at six?`,
          agent.name,
        );
      }
      if (age >= 4500 && task.call!.transcript.length === 1)
        addEvent(
          task,
          'transcript_line',
          'Of course. We have a table at six. There’s a £20 deposit to secure the booking.',
          'Restaurant',
        );
      if (age >= 6000) {
        if (agent.tools.includes('payments')) {
          task.status = 'awaiting_approval';
          task.payment = {
            id: `payment-${id}`,
            task_id: id,
            amount: 2000,
            currency: 'GBP',
            merchant: 'The Ivy Oxford',
            status: 'pending_approval',
          };
          addEvent(task, 'payment', 'Waiting for your approval');
        } else {
          task.status = 'failed';
          task.call!.status = 'ended';
          task.call!.ended_at = new Date().toISOString();
          task.summary =
            'The restaurant requires a deposit. Enable payments on a new agent to complete this demo booking.';
          addEvent(task, 'ended', 'Booking requires a payment tool');
        }
      }
    }
    save();
    return structuredClone(task);
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
      state().agents.find((a) => a.id === task.agent_id)!.name,
    );
    complete(task);
    save();
  },
  async calendar(): Promise<CalendarEvent[]> {
    return structuredClone(
      state().tasks.flatMap((t) => (t.calendar_event ? [t.calendar_event] : [])),
    );
  },
  async analytics(): Promise<Analytics> {
    const calls = state().tasks.filter((t) => t.call);
    const ended = calls.filter((t) => t.call?.ended_at);
    return {
      total_calls: calls.length,
      success_rate: ended.length
        ? (ended.filter((t) => t.status === 'done' && t.payment?.status !== 'denied').length /
            ended.length) *
          100
        : 0,
      avg_duration_seconds: ended.length
        ? ended.reduce(
            (s, t) => s + (Date.parse(t.call!.ended_at!) - Date.parse(t.call!.started_at)) / 1000,
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
      agents: state().agents.map((a) => {
        const tasks = ended.filter((t) => t.agent_id === a.id);
        return {
          name: a.name,
          calls: calls.filter((t) => t.agent_id === a.id).length,
          success_rate: tasks.length
            ? (tasks.filter((t) => t.status === 'done' && t.payment?.status !== 'denied').length /
                tasks.length) *
              100
            : 0,
        };
      }),
    };
  },
};
