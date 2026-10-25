import { money } from '../config';
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
/** Rows for the finished call's result table; null when the call produced nothing to summarise. */
export function bookingRows(task: Task): [string, string][] | null {
  const outcome = task.call?.outcome;
  const payment = task.payment;
  if (!task.call || !outcome) return null;
  const booked = Boolean(outcome.booked);
  const when = outcome.starts_at ? ukWallClock(outcome.starts_at) : null;
  const deposit = payment
    ? `${money(payment.amount, payment.currency)} · ${paymentStatus[payment.status]}`
    : outcome.deposit_required && outcome.deposit_amount_pence
      ? `${money(outcome.deposit_amount_pence, 'GBP')} · Still to pay`
      : null;
  const rows: [string, string | null | undefined][] = [
    ['Result', booked ? 'Confirmed' : 'Not confirmed'],
    ['Business', outcome.venue || payment?.merchant],
    ['Date', booked ? when?.date : null],
    ['Time', booked ? when?.time : null],
    ['Details', outcome.details],
    ['Name', booked ? outcome.booking_name : null],
    ['Deposit', deposit],
    [
      'Other times offered',
      !booked && outcome.offered_times?.length
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
      <caption>Call result</caption>
      <tbody>
        {rows.map(([label, value]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            <td
              className={
                label === 'Result' ? `booking-${value === 'Confirmed' ? 'ok' : 'no'}` : undefined
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
