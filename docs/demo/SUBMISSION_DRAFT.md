# Concierge

**One conversation for the everyday tasks that take too many steps.**

## Project description

Concierge gives each user a personal AI agent with explicit permission to use phone calls, email, calendar, and test payments. A request such as booking dinner becomes a tracked task: the agent calls, asks before a deposit, records the outcome, and keeps the plan accessible in task history and the calendar.

The frontend uses React, TypeScript, and Vite. FastAPI provides the API. The planned orchestration pairs Gemini function calling with ElevenLabs voice conversations and Twilio telephone connectivity. Tiger Data stores task and call events, and the deployment targets a Vultr VM with Caddy and systemd.

## What we built

A browser workspace for selecting and configuring agents, conversations with status and transcript cards, explicit payment approvals, calendar export, searchable history, and activity charts. The local fallback includes successful bookings, declined deposits, unanswered calls, fully booked restaurants, and agreed alternative times. Agent configurations can be edited or duplicated; deleting an agent preserves its completed history.

The API work includes agent management, joined task history, an internal calendar, .ics export, and a confirmation-email function. Tool permissions, retry handling, calendar idempotency, and provider idempotency keep repeated callbacks from creating duplicate side effects.

## Challenges and lessons

The important boundary is between planning a task and carrying out a phone conversation. A durable task/call contract lets the frontend show progress while services finish independently. Explicit payment approval creates a natural handoff back to the user. Live phone transcripts may require post-call replay, so the interface supports both streaming events and stored transcript recovery.

We built a deterministic simulation alongside the real-service adapters. That made it possible to develop, test failure cases, and record a fallback without making unnecessary calls or charges.

## Sponsor evidence to add before submission

- Gemini: Alex's actual function-call traces and structured extraction example.
- ElevenLabs: Jamil's real outbound call and server-tool integration.
- Tiger Data: hypertable/continuous aggregate queries and real analytics evidence.
- Vultr: the public HTTPS domain and deployed commit.
- DEV: final article URL, after all factual claims are verified.

## Publication gate

This is an unpublished draft. Replace planned integrations with verified implementation details only after they work on the deployed site. Add the final project title/team credits, deployed URL, repository URL, real demo video, and sponsor challenge selections. Do not present the fallback simulation as proof of real provider integration. Production rehearsals and external submission have not occurred yet.
