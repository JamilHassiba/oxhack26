-- The business each call was for, as the user named it. Owner: Jamil.
-- Every call rings the one CALL_NUMBER, so the business can't be found from the number dialled.
ALTER TABLE calls ADD COLUMN IF NOT EXISTS business_name text;
