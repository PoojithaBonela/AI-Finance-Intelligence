-- ============================================================================
-- Phase 3.1: Agent 3 (AI Insights) Database Foundation Migration
-- ============================================================================
--
-- Configuration:
--   - Model: gemini-embedding-2
--   - Dimension: 768
--   - Storage: Exactly one embedding per receipt (UNIQUE on receipt_id)
--   - Vector Index: No vector ANN index yet (to be added in later phase)
--
-- Instructions:
--   - Run this migration script in the Supabase SQL Editor.
-- ============================================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ----------------------------------------------------------------------------
-- 2. Create `conversations` Table
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 3. Create `messages` Table
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 4. Create `receipt_embeddings` Table
-- ----------------------------------------------------------------------------
-- Model: gemini-embedding-2
-- Dimension: 768
-- Storage: Exactly one embedding per receipt (UNIQUE on receipt_id)
CREATE TABLE IF NOT EXISTS receipt_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id UUID NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_receipt_embeddings_receipt_id UNIQUE (receipt_id)
);

-- ----------------------------------------------------------------------------
-- 5. Create Performance Indexes (B-Tree)
-- ----------------------------------------------------------------------------
-- Note: No vector ANN index yet (HNSW / IVFFlat will be added once data volume warrants it)
-- Conversations indexes
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);

-- Messages indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at ASC);

-- Receipt embeddings indexes
CREATE INDEX IF NOT EXISTS idx_receipt_embeddings_receipt_id ON receipt_embeddings(receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_embeddings_user_id ON receipt_embeddings(user_id);

-- ----------------------------------------------------------------------------
-- 6. Updated_at Timestamp Trigger
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_conversations_updated_at ON conversations;
CREATE TRIGGER trigger_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_receipt_embeddings_updated_at ON receipt_embeddings;
CREATE TRIGGER trigger_receipt_embeddings_updated_at
    BEFORE UPDATE ON receipt_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 7. Enable Row Level Security (RLS)
-- ----------------------------------------------------------------------------
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipt_embeddings ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 8. RLS Policies: `conversations`
-- ----------------------------------------------------------------------------
CREATE POLICY "Users can view own conversations"
    ON conversations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own conversations"
    ON conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own conversations"
    ON conversations FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own conversations"
    ON conversations FOR DELETE
    USING (auth.uid() = user_id);

-- ----------------------------------------------------------------------------
-- 9. RLS Policies: `messages` (Inherits ownership via `conversations`)
-- ----------------------------------------------------------------------------
CREATE POLICY "Users can view messages from own conversations"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
              AND conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert messages into own conversations"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
              AND conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update messages in own conversations"
    ON messages FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
              AND conversations.user_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
              AND conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete messages from own conversations"
    ON messages FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM conversations
            WHERE conversations.id = messages.conversation_id
              AND conversations.user_id = auth.uid()
        )
    );

-- ----------------------------------------------------------------------------
-- 10. RLS Policies: `receipt_embeddings`
-- ----------------------------------------------------------------------------
CREATE POLICY "Users can view own receipt embeddings"
    ON receipt_embeddings FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own receipt embeddings"
    ON receipt_embeddings FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own receipt embeddings"
    ON receipt_embeddings FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own receipt embeddings"
    ON receipt_embeddings FOR DELETE
    USING (auth.uid() = user_id);
