<!-- Contract between Jamil, Alex and Evan: call_events kinds and payloads, the CallBrief format,
start_call / on_call_finished, and payment statuses. Owner: Jamil. -->

# Call events

Everything that happens during a phone call is written as a row in the `call_events` hypertable (Tiger Data). The UI reads these rows to show the live transcript and the call timeline.

- **Written by:** Jamil's code (`services/events.py`): the call lifecycle, ElevenLabs webhooks, and the mid-call payment tool.
- **Read by:** Evan's `GET /tasks/{id}` (as `task.events`) and the live stream `GET /calls/{id}/events/stream`.
- **Frontend type:** `CallEvent` in `frontend/src/types.ts`. Backend model: `CallEvent` in `backend/app/evan/models.py`.

If you change anything here, tell the other two first.

## Row shape

```json
{
  "ts": "2026-10-24T18:02:13.481Z",
  "call_id": "6f1c...-uuid",
  "kind": "transcript_line",
  "payload": { "speaker": "Maya", "text": "Hi, I'd like to book a table for four." }
}
```

| Field | Type | Notes |
|---|---|---|
| `ts` | timestamp with time zone | When it happened. Must be unique within a call (see rules). |
| `call_id` | uuid (string in the API) | The `calls` row this event belongs to. |
| `kind` | text | One of the kinds below. Enforced by the database. |
| `payload` | json object | The details of the event (nothing to do with payments). Always has `text`. Other fields depend on the kind. |

Think of the events as a diary of the call: one row per thing that happened. Only things that actually happen are written, so a call with no deposit simply has no `payment` event.

## Kinds

| Kind | When | Payload | Written by |
|---|---|---|---|
| `dialing` | `start_call` has started the outbound call | `text`, `to_number` | `start_call` |
| `ringing` | The other phone is ringing (only if ElevenLabs/Twilio tells us) | `text` | call status updates |
| `answered` | Someone picked up | `text` | call status updates |
| `transcript_line` | One line of the conversation | `text`, `speaker` | transcript (live or replayed, see open question) |
| `tool_call` | The voice agent used a server tool mid-call | `text`, `tool`, `args` | `/webhooks/elevenlabs/tools/{name}` |
| `payment` | The voice agent asked for a payment approval | `text`, `payment_id`, `amount`, `currency` | `request_payment_approval` tool |
| `ended` | The call is over | `text`, `reason`, `duration_seconds` | post-call webhook |

`reason` on `ended` is one of: `completed`, `no_answer`, `busy`, `voicemail`, `failed`.

Gemini's own tool calls (before and after the phone call) are **not** call events, because there's no call yet. They're logged by the orchestrator.

## Rules

1. **`text` is always present and human-readable.** The UI shows it as the label in the timeline. Example: `"Calling The Ivy Oxford"`, `"Waiting for your approval: £20.00"`.
2. **`speaker` on transcript lines:** the agent's name (e.g. `"Maya"`) for the AI's lines, the contact's name (e.g. `"The Ivy Oxford"`) for the other person. The UI styles a line as the agent's when `speaker` equals the agent name.
3. **Timestamps must be unique per call.** The UI removes events with the same `ts`, `kind` and `payload`. Insert with `clock_timestamp()`, not `now()`, because `now()` is the same for every row in one transaction.
4. **Extra payload fields are fine.** The UI only reads `speaker` and `text` and ignores the rest.
5. **Money is in minor units:** `amount: 2000` means £20.00.
6. **Events are only ever added**, never updated or deleted. Order by `ts`.

## Live stream

`GET /calls/{id}/events/stream` (server-sent events):

- Sends existing events for the call first, then new ones as they're written.
- Each message: `event: <kind>`, `id: <ts>`, `data: <the row as JSON>`. The `id` lets the browser resume after a reconnect.
- Closes after the `ended` event.

## Example: booking a table

| ts | kind | payload |
|---|---|---|
| 18:02:01 | `dialing` | `{"text": "Calling The Ivy Oxford", "to_number": "+44..."}` |
| 18:02:06 | `answered` | `{"text": "Connected"}` |
| 18:02:07 | `transcript_line` | `{"speaker": "Maya", "text": "Hi, I'm Maya, an AI assistant calling on behalf of Jamil..."}` |
| 18:02:12 | `transcript_line` | `{"speaker": "The Ivy Oxford", "text": "Sure, we have a table at six. There's a £20 deposit."}` |
| 18:02:14 | `payment` | `{"text": "Waiting for your approval: £20.00", "payment_id": "...", "amount": 2000, "currency": "GBP"}` |
| 18:02:31 | `transcript_line` | `{"speaker": "Maya", "text": "The deposit is approved. Thank you!"}` |
| 18:02:40 | `ended` | `{"text": "Call finished", "reason": "completed", "duration_seconds": 39}` |

## Related contracts

- **`start_call(brief) -> call_id`** and **`on_call_finished(call_id)`**, and the `CallBrief` fields: `backend/app/contracts.py`.
- **Payment statuses:** `pending_approval` → `approved` → `paid`, or `pending_approval` → `denied`. Also in `contracts.py`.
- **Table definitions:** `backend/migrations/001_init.sql`.

## Open question: live transcript

Not yet known whether ElevenLabs gives us transcript lines **during** a phone call or only in the post-call webhook. Jamil's voice spike will answer this.

- **If live:** write `transcript_line` events as they arrive.
- **If post-call only:** the post-call webhook writes all `transcript_line` events at the end, spaced by their real timings, so the UI can replay them. The other events (`dialing`, `payment`, `ended`) are still live.
