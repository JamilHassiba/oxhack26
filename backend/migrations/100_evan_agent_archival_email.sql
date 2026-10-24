-- Additive to Jamil's 001_init.sql. Apply only after the agreed base tables exist.
-- Soft deletion preserves task, call, payment, and calendar foreign keys.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS archived_at timestamptz;
CREATE TABLE IF NOT EXISTS email_deliveries (
    task_id uuid PRIMARY KEY REFERENCES tasks(id),
    provider_id text NOT NULL,
    fingerprint text NOT NULL,
    sent_at timestamptz NOT NULL DEFAULT now()
);
-- Pair the delete route's row lock with task inserts so archiving cannot race a new task.
CREATE OR REPLACE FUNCTION evan_require_active_agent() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM id FROM agents WHERE id = NEW.agent_id AND archived_at IS NULL FOR KEY SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cannot create a task for an archived or missing agent' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS evan_tasks_require_active_agent ON tasks;
CREATE TRIGGER evan_tasks_require_active_agent BEFORE INSERT ON tasks
    FOR EACH ROW EXECUTE FUNCTION evan_require_active_agent();
