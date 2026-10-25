import { TIME_ZONE, money } from '../config';
import type { Task } from '../types';

const paymentStatus = {
  pending_approval: 'Awaiting your approval',
  approved: 'Approved',
  paid: 'Paid',
  denied: 'Declined',
} as const;

/** "2026-10-26T18:30" (UK wall-clock time, no offset) -> { date: "Mon 26 Oct", time: "18:30" }. */
function ukWallClock(value: string) {
  const [day, time = ''] = value.split('T');
  const [y, m, d] = day.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-GB', {
    timeZone: 'UTC',
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
  return { date, time: time.slice(0, 5) };
}
/** An ISO instant (e.g. a calendar event) shown in UK time. */
function ukInstant(value: string) {
  const at = new Date(value);
  const opts = { timeZone: TIME_ZONE } as const;
  return {
    date: at.toLocaleDateString('en-GB', {
      ...opts,
      weekday: 'short',
      day: 'numeric',
      month: 'short',
    }),
    time: at.toLocaleTimeString('en-GB', { ...opts, hour: '2-digit', minute: '2-digit' }),
  };
}

/** Rows for the finished call's booking table; null when the call produced nothing to summarise. */
export function bookingRows(task: Task): [string, string][] | null {
  const outcome = task.call?.outcome;
  const event = task.calendar_event;
  const payment = task.payment;
  if (!task.call || (!outcome && !event)) return null;
  const booked = outcome?.booked ?? Boolean(event);
  const when = outcome?.starts_at
    ? ukWallClock(outcome.starts_at)
    : event
      ? ukInstant(event.starts_at)
      : null;
  const deposit = payment
    ? `${money(payment.amount, payment.currency)} · ${paymentStatus[payment.status]}`
    : outcome?.deposit_required && outcome.deposit_amount_pence
      ? `${money(outcome.deposit_amount_pence, 'GBP')} · Still to pay`
      : 'None';
  const rows: [string, string | null | undefined][] = [
    ['Booking', booked ? 'Confirmed' : 'Not booked'],
    ['Venue', outcome?.venue || event?.location || payment?.merchant],
    ['Date', booked ? when?.date : null],
    ['Time', booked ? when?.time : null],
    ['Party size', outcome?.party_size ? `${outcome.party_size} people` : null],
    ['Name on booking', booked ? outcome?.booking_name : null],
    ['Deposit', booked || payment ? deposit : null],
    [
      'Other times offered',
      !booked && outcome?.offered_times?.length
        ? outcome.offered_times.map((t) => ukWallClock(t).time).join(', ')
        : null,
    ],
  ];
  return rows.filter((row): row is [string, string] => Boolean(row[1]));
}

export function BookingSummary({ task }: { task: Task }) {
  const rows = bookingRows(task);
  if (!rows) return null;
  return (
    <table className="booking-summary">
      <caption>Booking details</caption>
      <tbody>
        {rows.map(([label, value]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            <td
              className={
                label === 'Booking' ? `booking-${value === 'Confirmed' ? 'ok' : 'no'}` : undefined
              }
            >
              {value}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
