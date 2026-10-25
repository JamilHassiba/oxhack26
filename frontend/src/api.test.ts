import { afterEach, describe, expect, it, vi } from 'vitest';
import { request } from './api';
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
