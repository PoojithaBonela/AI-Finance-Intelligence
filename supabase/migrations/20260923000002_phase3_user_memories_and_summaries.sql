-- ============================================================================
-- Phase 3.6: User Memories & Conversation Summaries Migration
-- ============================================================================
--
-- Purpose:
--   1. Adds conversation summary fields to `conversations` (Layer 2 memory).
--   2. Creates dedicated `user_memories` table for cross-chat durable context (Layer 3 memory).
--   3. Implements strict Row Level Security (RLS) for user memories.
--   4. Creates `match_user_memories` RPC for pgvector semantic memory search.
--   5. Configures secure function execution permissions.
--
-- Configuration:
--   - Embedding Model: gemini-embedding-2
--   - Embedding Dimension: 768
--   - Memory Types: 'preference', 'financial_goal', 'profile', 'context'
--
-- Instructions:
--   - Run this migration script in the Supabase SQL Editor.
--   - Do NOT execute directly from the backend.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Extend `conversations` for Layer 2 Conversation Summaries
-- ----------------------------------------------------------------------------
ALTER TABLE conversations 
    ADD COLUMN IF NOT EXISTS summary TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS summarized_through_message_id UUID REFERENCES messages(id) ON DELETE SET NULL;

-- ----------------------------------------------------------------------------
-- 2. Create `user_memories` Table (Layer 3 Cross-Chat Memory)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('preference', 'financial_goal', 'profile', 'context')),
    memory_text TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    source_conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    source_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.00 CHECK (confidence BETWEEN 0.00 AND 1.00),
    importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 3. Performance Indexes (B-Tree)
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_conversations_summarized_msg_id ON conversations(summarized_through_message_id);
CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON user_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_user_memories_is_active ON user_memories(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_memories_last_used ON user_memories(user_id, last_used_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_memories_source_conv ON user_memories(source_conversation_id);

-- ----------------------------------------------------------------------------
-- 4. Updated_at Trigger for `user_memories`
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trigger_user_memories_updated_at ON user_memories;
CREATE TRIGGER trigger_user_memories_updated_at
    BEFORE UPDATE ON user_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 5. Enable Row Level Security (RLS) on `user_memories`
-- ----------------------------------------------------------------------------
ALTER TABLE user_memories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own memories"
    ON user_memories FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own memories"
    ON user_memories FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own memories"
    ON user_memories FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own memories"
    ON user_memories FOR DELETE
    USING (auth.uid() = user_id);

-- ----------------------------------------------------------------------------
-- 6. Dedicated Semantic Search RPC: `match_user_memories`
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_user_memories (
    query_embedding vector(768),
    match_user_id uuid,
    match_threshold double precision DEFAULT 0.60,
    match_count int DEFAULT 5,
    filter_type text DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    memory_type text,
    memory_text text,
    importance int,
    similarity double precision
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
    -- Defense-in-depth: If invoked by an authenticated client session, verify match_user_id matches auth.uid()
    IF auth.role() = 'authenticated' AND auth.uid() IS DISTINCT FROM match_user_id THEN
        RAISE EXCEPTION 'Forbidden: match_user_id does not match the authenticated session.';
    END IF;

    RETURN QUERY
    SELECT
        um.id,
        um.memory_type,
        um.memory_text,
        um.importance,
        ROUND((1 - (um.embedding <=> query_embedding))::numeric, 4)::double precision AS similarity
    FROM user_memories um
    WHERE um.user_id = match_user_id
      AND um.is_active = true
      AND (filter_type IS NULL OR um.memory_type = filter_type)
      AND (1 - (um.embedding <=> query_embedding)) >= match_threshold
    ORDER BY um.embedding <=> query_embedding ASC
    LIMIT match_count;
END;
$$;

-- ----------------------------------------------------------------------------
-- 7. Permissions & Access Control for `match_user_memories`
-- ----------------------------------------------------------------------------
REVOKE EXECUTE ON FUNCTION match_user_memories(vector, uuid, double precision, int, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION match_user_memories(vector, uuid, double precision, int, text) FROM anon;

GRANT EXECUTE ON FUNCTION match_user_memories(vector, uuid, double precision, int, text) TO service_role;
GRANT EXECUTE ON FUNCTION match_user_memories(vector, uuid, double precision, int, text) TO authenticated;
