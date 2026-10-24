-- Initial schema: users, agents, messages, tasks, calls, payments, calendar_events,
-- and the call_events hypertable (Tiger Data). Owner: Jamil. See docs/DESIGN.md section 4.
--
-- IDs are uuid in the DB and strings in Python/the API (see backend/app/contracts.py).
-- Row shapes follow frontend/src/types.ts, which is the API contract.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE users (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,
    email      text,
    phone      text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                text NOT NULL,
    persona             text NOT NULL DEFAULT '',
    voice               text NOT NULL DEFAULT 'Warm & natural',  -- label; mapped to an ElevenLabs voice ID in code
    tools               jsonb NOT NULL DEFAULT '[]',              -- subset of ["phone","email","calendar","payments"]
    elevenlabs_agent_id text,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX agents_user_id_idx ON agents (user_id);

-- Businesses the agent can call. Gemini finds numbers here via lookup_contact.
CREATE TABLE contacts (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,
    phone      text NOT NULL,  -- E.164, e.g. +447700900123
    notes      text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id   uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    goal       text NOT NULL,
    status     text NOT NULL DEFAULT 'planning'
               CHECK (status IN ('planning', 'calling', 'awaiting_approval', 'done', 'failed')),
    summary    text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tasks_agent_id_created_at_idx ON tasks (agent_id, created_at);

CREATE TABLE messages (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id   uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    task_id    uuid REFERENCES tasks(id) ON DELETE CASCADE,
    role       text NOT NULL CHECK (role IN ('user', 'assistant')),
    content    text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX messages_agent_id_created_at_idx ON messages (agent_id, created_at);

CREATE TABLE calls (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id            uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    to_number          text NOT NULL,
    el_conversation_id text UNIQUE,                  -- ElevenLabs conversation ID, set once the call starts
    status             text NOT NULL DEFAULT 'dialing',
    started_at         timestamptz NOT NULL DEFAULT now(),
    ended_at           timestamptz,
    transcript         jsonb NOT NULL DEFAULT '[]',  -- [{speaker, text}]
    summary            text,
    outcome            jsonb                         -- structured result, e.g. {booked, time, deposit}
);
CREATE INDEX calls_task_id_idx ON calls (task_id);

CREATE TABLE payments (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id      uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    call_id      uuid REFERENCES calls(id) ON DELETE SET NULL,
    amount       integer NOT NULL CHECK (amount > 0),  -- minor units: 2000 = £20.00
    currency     text NOT NULL DEFAULT 'GBP',
    merchant     text,
    description  text NOT NULL DEFAULT '',
    status       text NOT NULL DEFAULT 'pending_approval'
                 CHECK (status IN ('pending_approval', 'approved', 'paid', 'denied')),
    stripe_pi_id text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX payments_task_id_idx ON payments (task_id);

CREATE TABLE calendar_events (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id    uuid REFERENCES tasks(id) ON DELETE SET NULL,
    title      text NOT NULL,
    starts_at  timestamptz NOT NULL,
    ends_at    timestamptz NOT NULL,
    location   text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX calendar_events_starts_at_idx ON calendar_events (starts_at);

-- Time-series log of everything that happens on a call. Kinds and payloads: docs/EVENTS.md.
CREATE TABLE call_events (
    ts      timestamptz NOT NULL DEFAULT now(),
    call_id uuid NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    kind    text NOT NULL
            CHECK (kind IN ('dialing', 'ringing', 'answered', 'transcript_line', 'tool_call', 'payment', 'ended')),
    payload jsonb NOT NULL DEFAULT '{}'
);
SELECT create_hypertable('call_events', by_range('ts', INTERVAL '1 day'));
CREATE INDEX call_events_call_id_ts_idx ON call_events (call_id, ts);

-- Seed data. Fixed IDs so code and tests can refer to them.
INSERT INTO users (id, name) VALUES ('00000000-0000-0000-0000-000000000001', 'Demo User');

-- Demo restaurant. The real number (a teammate's phone) is set locally, never committed:
--   UPDATE contacts SET phone = '+44...' WHERE name = 'The Ivy Oxford';
INSERT INTO contacts (name, phone, notes)
VALUES ('The Ivy Oxford', '+440000000000', 'Demo restaurant. Calls go to a teammate playing the restaurant.');
