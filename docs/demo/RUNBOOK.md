# Demo runbook

## Two-minute presentation

**0:00–0:15 — Problem.** Everyday bookings mean phone queues, deposits, and calendar admin. Concierge puts those steps into one conversation.

**0:15–0:30 — Agent.** Choose Maya with the arrow controls. Show the phone, email, calendar, and payment checkboxes, then Enter agent. Tool access is explicit and every payment needs approval.

**0:30–1:15 — Request.** Ask for a table for four at the seeded demo restaurant at 18:00, with 19:00 as a fallback. The restaurant contact must point to a teammate playing the restaurant. Watch call status and transcript. Explain the split: Gemini plans, ElevenLabs handles the conversation, Tiger Data stores the events.

**1:15–1:40 — Approval and result.** The teammate asks for a £20 test deposit. Approve it in the UI. Show the summary, confirmed calendar entry, and export. Show the confirmation email only after actual delivery is verified.

**1:40–2:00 — Evidence and close.** Open History and the task transcript, then Analytics. Mention Vultr hosting only when showing the working deployed domain. Close with the benefit: one request instead of several administrative steps.

## Fallback

`fallback-demo.webm` is a recorded **simulation**, not evidence of a real telephone booking or payment. It shows agent permissions, a simulated call, manual deposit approval, history, calendar, and analytics. Be explicit about using demo mode if production calls fail.

Regenerate locally:

```sh
cd frontend
npm ci
npx playwright install chromium
cd ..
node scripts/record-demo.mjs
```

This creates an isolated browser context, uses a local demo-only server, and saves video/screenshots here. It never contacts the real backend or payment/phone/email providers. Recorded times/metrics are fixtures from that recording, not performance benchmarks.

## Production rehearsal checklist

Run the full real-service flow three times after deployment and integration. Do not mark these complete based on the local simulation.

| Rehearsal | URL / commit | Actual call / transcript | Approval / test payment | Calendar / email | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | Pending VM/domain | Pending | Pending | Pending | Not run |
| 2 | Pending VM/domain | Pending | Pending | Pending | Not run |
| 3 | Pending VM/domain | Pending | Pending | Pending | Not run |

Also verify: declined deposit creates no reservation; no answer produces a failed task and unlocks chat; a fully booked restaurant uses only the approved fallback; disabled tools cannot execute; refresh during a call restores history; changing laptops still loads server tasks. Use Stripe test credentials and the allowlisted teammate's phone.

External prerequisites: Vultr VM/domain, Jamil's DB/migrations/voice/events, Alex's main app/chat/payments, Resend verified sender, and test provider credentials.
