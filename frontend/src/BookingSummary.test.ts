import { describe, expect, it } from 'vitest';
import { bookingRows } from './components/BookingSummary';
import type { Task } from './types';

const base: Task = {
  id: 't1',
  agent_id: 'a1',
  goal: 'Book a table for 4 at The Ivy Oxford tomorrow at 6pm',
  status: 'done',
  created_at: '2026-10-25T01:00:00Z',
  events: [],
  call: {
    id: 'c1',
    status: 'ended',
    started_at: '2026-10-25T01:11:21Z',
    ended_at: '2026-10-25T01:12:28Z',
    transcript: [],
  },
};

describe('call result rows', () => {
  it('shows the booking from the call outcome, in UK time', () => {
    const rows = bookingRows({
      ...base,
      call: {
        ...base.call!,
        outcome: {
          booked: true,
          starts_at: '2026-10-26T18:30',
          details: 'table for 4',
          booking_name: 'Alex',
          venue: 'The Ivy Oxford',
          deposit_required: true,
          deposit_amount_pence: 2000,
        },
      },
      payment: { id: 'p1', task_id: 't1', amount: 2000, currency: 'GBP', status: 'paid' },
    });
    expect(rows).toEqual([
      ['Result', 'Confirmed'],
      ['Business', 'The Ivy Oxford'],
      ['Date', 'Mon 26 Oct'],
      ['Time', '18:30'],
      ['Details', 'table for 4'],
      ['Name', 'Alex'],
      ['Deposit', '£20.00 · Paid'],
    ]);
  });

  it('explains a call that did not book, with the times offered', () => {
    const rows = bookingRows({
      ...base,
      status: 'failed',
      call: {
        ...base.call!,
        outcome: {
          booked: false,
          venue: 'The Ivy Oxford',
          details: 'table for 4',
          offered_times: ['2026-10-26T20:30', '2026-10-26T21:00'],
        },
      },
    });
    expect(rows).toEqual([
      ['Result', 'Not confirmed'],
      ['Business', 'The Ivy Oxford'],
      ['Details', 'table for 4'],
      ['Other times offered', '20:30, 21:00'],
    ]);
  });

  it('shows nothing for tasks without a call or a result', () => {
    expect(bookingRows({ ...base, call: undefined })).toBeNull();
    expect(bookingRows(base)).toBeNull();
  });
});
