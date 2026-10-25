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

describe('booking summary rows', () => {
  it('shows the booking from the call outcome, in UK time', () => {
    const rows = bookingRows({
      ...base,
      call: {
        ...base.call!,
        outcome: {
          booked: true,
          starts_at: '2026-10-26T18:30',
          party_size: 4,
          booking_name: 'Alex',
          venue: 'The Ivy Oxford',
          deposit_required: true,
          deposit_amount_pence: 2000,
        },
      },
      payment: { id: 'p1', task_id: 't1', amount: 2000, currency: 'GBP', status: 'paid' },
    });
    expect(rows).toEqual([
      ['Booking', 'Confirmed'],
      ['Venue', 'The Ivy Oxford'],
      ['Date', 'Mon 26 Oct'],
      ['Time', '18:30'],
      ['Party size', '4 people'],
      ['Name on booking', 'Alex'],
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
          party_size: 4,
          offered_times: ['2026-10-26T20:30', '2026-10-26T21:00'],
        },
      },
    });
    expect(rows).toEqual([
      ['Booking', 'Not booked'],
      ['Venue', 'The Ivy Oxford'],
      ['Party size', '4 people'],
      ['Other times offered', '20:30, 21:00'],
    ]);
  });

  it('falls back to the calendar event when there is no outcome (demo mode)', () => {
    const rows = bookingRows({
      ...base,
      calendar_event: {
        id: 'e1',
        task_id: 't1',
        title: 'Dinner',
        starts_at: '2026-10-26T18:30:00Z', // 26 Oct is GMT, so 18:30 UK
        ends_at: '2026-10-26T20:00:00Z',
        location: 'The Ivy Oxford',
      },
    });
    expect(rows).toEqual([
      ['Booking', 'Confirmed'],
      ['Venue', 'The Ivy Oxford'],
      ['Date', 'Mon 26 Oct'],
      ['Time', '18:30'],
      ['Deposit', 'None'],
    ]);
  });

  it('shows nothing for tasks without a call or a result', () => {
    expect(bookingRows({ ...base, call: undefined })).toBeNull();
    expect(bookingRows(base)).toBeNull();
  });
});
