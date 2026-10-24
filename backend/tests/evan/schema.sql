-- Test-only agreed base schema. This is not Jamil's production migration.
CREATE TABLE users (id uuid PRIMARY KEY, email text NOT NULL, name text NOT NULL, phone text);
CREATE TABLE agents (id uuid PRIMARY KEY, user_id uuid REFERENCES users(id), name text NOT NULL, persona text NOT NULL, voice text NOT NULL, tools jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE tasks (id uuid PRIMARY KEY, agent_id uuid NOT NULL REFERENCES agents(id), goal text NOT NULL, status text NOT NULL, summary text, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE calls (id uuid PRIMARY KEY, task_id uuid REFERENCES tasks(id), status text NOT NULL, started_at timestamptz, ended_at timestamptz, transcript jsonb, summary text, outcome jsonb, el_conversation_id text, to_number text);
CREATE TABLE payments (id uuid PRIMARY KEY, task_id uuid REFERENCES tasks(id), amount integer NOT NULL, currency text NOT NULL, merchant text, status text NOT NULL, stripe_pi_id text);
CREATE TABLE calendar_events (id uuid PRIMARY KEY, task_id uuid REFERENCES tasks(id), title text NOT NULL, starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL, location text NOT NULL DEFAULT '');
CREATE TABLE call_events (ts timestamptz NOT NULL, call_id uuid REFERENCES calls(id), kind text NOT NULL, payload jsonb NOT NULL);
