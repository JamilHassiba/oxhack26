import { Phone, Mail, CalendarDays, CreditCard } from 'lucide-react';
import type { Tool } from './types';
export const tools = {
  phone: { label: 'Phone calls', icon: Phone, description: 'Make calls on your behalf' },
  email: { label: 'Email', icon: Mail, description: 'Send confirmation emails' },
  calendar: { label: 'Calendar', icon: CalendarDays, description: 'Keep your plans in one place' },
  payments: {
    label: 'Payments',
    icon: CreditCard,
    description: 'Test payments, with your approval',
  },
};
export const shortcuts = {
  call: {
    label: 'Make a call',
    icon: Phone,
    tool: 'phone' as Tool,
    prompt: 'Book a table for 4 at The Ivy Oxford tomorrow at 6pm. They may ask for a £20 deposit.',
  },
  email: {
    label: 'Send an email',
    icon: Mail,
    tool: 'email' as Tool,
    prompt: 'Draft and send an email. Ask me for the recipient and message before sending.',
  },
  calendar: {
    label: 'Plan my day',
    icon: CalendarDays,
    tool: 'calendar' as Tool,
    prompt: 'Help me organise my schedule for tomorrow.',
  },
};
// Bookings are at UK venues: always show UK time, whatever the viewer's own time zone.
export const TIME_ZONE = 'Europe/London';
export const dateTime = (date: string) =>
  new Date(date).toLocaleString('en-GB', {
    timeZone: TIME_ZONE,
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
export const money = (amount: number, currency: string) =>
  new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount / 100);
export const labels = {
  planning: 'Thinking it through',
  calling: 'On the call',
  awaiting_approval: 'Needs your approval',
  done: 'Completed',
  failed: 'Needs attention',
};
