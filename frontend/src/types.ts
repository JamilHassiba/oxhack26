// Provisional contract from docs/DESIGN.md §4–5. Generate openapi.d.ts once FastAPI lands.
export type Tool = 'phone' | 'email' | 'calendar' | 'payments';
export type Agent = { id: string; name: string; voice: string; tools: Tool[] };
export type AgentInput = Omit<Agent, 'id'>;
export type TaskStatus = 'planning' | 'calling' | 'awaiting_approval' | 'done' | 'failed';
export type CallEvent = {
  ts: string;
  call_id: string;
  kind: 'dialing' | 'ringing' | 'answered' | 'transcript_line' | 'tool_call' | 'payment' | 'ended';
  payload: { text?: string; speaker?: string };
};
export type Payment = {
  id: string;
  task_id: string;
  amount: number;
  currency: string;
  merchant?: string;
  status: 'pending_approval' | 'approved' | 'paid' | 'denied';
};
export type CalendarEvent = {
  id: string;
  task_id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  location: string;
};
export type CallOutcome = {
  result?: string | null;
  booked?: boolean | null;
  /** UK wall-clock time without an offset, e.g. "2026-10-26T18:30". */
  starts_at?: string | null;
  party_size?: number | null;
  booking_name?: string | null;
  venue?: string | null;
  deposit_required?: boolean | null;
  deposit_amount_pence?: number | null;
  offered_times?: string[];
  reason?: string | null;
};
export type Task = {
  id: string;
  agent_id: string;
  goal: string;
  status: TaskStatus;
  summary?: string;
  created_at: string;
  call?: {
    id: string;
    status: string;
    started_at: string;
    ended_at?: string;
    transcript: { speaker: string; text: string }[];
    /** What the call achieved, extracted by Gemini after the call; absent until then (and in demo mode). */
    outcome?: CallOutcome | null;
  };
  payment?: Payment;
  calendar_event?: CalendarEvent;
  events: CallEvent[];
};
export type Message = {
  id: string;
  agent_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
};
export type Analytics = {
  total_calls: number;
  success_rate: number;
  avg_duration_seconds: number;
  calls_by_day: { date: string; calls: number }[];
  agents: { name: string; calls: number; success_rate: number }[];
};
