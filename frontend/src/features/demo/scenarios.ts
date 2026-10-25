// These fixtures belong to the local simulator, never to the backend API contract.
export const scenarios = {
  success: {
    label: 'Successful booking',
    description: 'Approve the £20 test deposit to confirm.',
    prompt: 'Book a table for 4 at The Ivy Oxford tomorrow at 6pm. They may ask for a £20 deposit.',
  },
  declined_deposit: {
    label: 'Declined deposit',
    description: 'Choose Decline when the deposit appears.',
    prompt:
      'Ask The Ivy Oxford for a table for 4 tomorrow at 6pm. Ask me before paying any deposit.',
  },
  no_answer: {
    label: 'No answer',
    description: 'The restaurant does not pick up.',
    prompt: 'Call The Ivy Oxford to book a table for 4 tomorrow at 6pm.',
  },
  fully_booked: {
    label: 'Fully booked',
    description: 'No tables are available. No payment is requested.',
    prompt: 'Book a table for 4 at The Ivy Oxford tomorrow evening. Check for availability.',
  },
  alternative_time: {
    label: 'Alternative time',
    description: '6pm is full; your agent books the agreed 7pm fallback.',
    prompt:
      'Book a table for 4 at The Ivy Oxford tomorrow at 6pm. 7pm is also fine if 6pm is full.',
  },
} as const;
export type DemoScenario = keyof typeof scenarios;
export function isDemoScenario(value: unknown): value is DemoScenario {
  return typeof value === 'string' && Object.hasOwn(scenarios, value);
}
/** There is no scenario picker: typing a scenario's exact prompt plays that scenario; otherwise
 * "no answer" or "fail" plays an unanswered call and anything else a successful booking. */
export function scenarioFor(goal: string): DemoScenario {
  const text = goal.trim();
  const match = (Object.keys(scenarios) as DemoScenario[]).find(
    (id) => scenarios[id].prompt === text,
  );
  return match ?? (/\b(fail|no answer)\b/i.test(text) ? 'no_answer' : 'success');
}
