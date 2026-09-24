-- ============================================================================
-- Phase 3.6 Step 4: Add Metadata to Messages Table
-- ============================================================================
--
-- Description:
--   Adds a JSONB `metadata` column to the `messages` table with a default of '{}'::jsonb.
--   This column stores operational agent execution metadata, such as:
--     - tools_used: list of tools invoked by Agent 3
--     - rounds_used: number of reasoning/tool turns used
--
-- Instructions:
--   - Run this migration script in the Supabase SQL Editor.
-- ============================================================================

ALTER TABLE messages
ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

-- GIN index for efficient JSONB querying/indexing on message metadata
CREATE INDEX IF NOT EXISTS idx_messages_metadata ON messages USING gin (metadata);
