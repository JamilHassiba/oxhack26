import { afterEach, describe, expect, it, vi } from 'vitest';
import { calendarIcs, request } from './api';
afterEach(() => vi.unstubAllGlobals());
describe('HTTP adapter', () => {
  it('surfaces backend error details', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: 'Payment already denied' }), { status: 409 }),
        ),
    );
    await expect(request('/payments/id/approve')).rejects.toThrow('Payment already denied');
  });
  it('accepts empty successful mutation responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    expect(await request('/payments/id/approve')).toBeUndefined();
  });
});
describe('calendar export', () => {
  it('escapes event text and uses UTC timestamps', () => {
    const ics = calendarIcs([
      {
        id: 'a',
        task_id: 'b',
        title: 'Dinner, friends; fun\nSecond line',
        location: 'Oxford',
        starts_at: '2026-10-25T18:00:00Z',
        ends_at: '2026-10-25T19:30:00Z',
      },
    ]);
    expect(ics).toContain('DTSTART:20261025T180000Z\r\n');
    expect(ics).toContain('SUMMARY:Dinner\\, friends\\; fun\\nSecond line');
    expect(ics).toContain('UID:a@concierge');
    expect(ics.endsWith('END:VCALENDAR\r\n')).toBe(true);
  });
});
