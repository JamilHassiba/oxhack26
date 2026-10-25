import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Phone,
  Sparkles,
  Check,
  CircleHelp,
  CheckCheck,
  Radio,
  CreditCard,
  ShieldCheck,
  PhoneOff,
} from 'lucide-react';
import { api, BASE, DEMO } from '../api';
import { labels, money } from '../config';
import { ErrorNotice } from './ui';
import { BookingSummary } from './BookingSummary';
import type { Agent, CallEvent, Task, Payment } from '../types';
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
export function TaskCard({ task, agent }: { task: Task; agent: Agent }) {
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
  const callLive =
    !DEMO &&
    running &&
    !!task.call &&
    !task.call.ended_at &&
    !events.some((e) => e.kind === 'ended');
  // While the call is live, keep the newest line in view as the conversation comes in.
  const lastLine = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (running) lastLine.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [running, transcript.length]);
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
      {callLive && task.call && <HangUpButton callId={task.call.id} />}
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
                  ref={i === transcript.length - 1 ? lastLine : undefined}
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
      {!running && <BookingSummary task={task} />}
    </div>
  );
}
function HangUpButton({ callId }: { callId: string }) {
  // Stays "Hanging up…" after success: the card switches over when the call's `ended` event arrives.
  const hangUp = useMutation({ mutationFn: () => api.hangUp(callId) });
  return (
    <div className="hang-up">
      <button
        className="danger"
        onClick={() => hangUp.mutate()}
        disabled={hangUp.isPending || hangUp.isSuccess}
      >
        <PhoneOff size={16} /> {hangUp.isPending || hangUp.isSuccess ? 'Hanging up…' : 'Hang up'}
      </button>
      {hangUp.isError && <ErrorNotice error={hangUp.error} />}
    </div>
  );
}
export function PaymentCard({ payment, agentId }: { payment: Payment; agentId: string }) {
  const client = useQueryClient();
  const decision = useMutation({
    mutationFn: (approve: boolean) => api.decide(payment.id, approve),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['tasks', agentId] });
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
