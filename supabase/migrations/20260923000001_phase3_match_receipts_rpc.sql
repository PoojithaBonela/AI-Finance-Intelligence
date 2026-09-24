-- ============================================================================
-- Phase 3.3: Agent 3 RAG Retrieval RPC (match_receipts)
-- ============================================================================
--
-- Purpose:
--   Performs pgvector cosine similarity search on `receipt_embeddings`
--   to retrieve top-K receipts for Agent 3 semantic questions.
--
-- Security:
--   - Strict user isolation: re.user_id = match_user_id AND r.user_id = match_user_id
--   - Soft-delete exclusion: r.deleted_at IS NULL
--   - Search path fixed: SET search_path = public, extensions (guards SECURITY DEFINER)
--   - Auth guard: If called with an authenticated JWT, enforces auth.uid() = match_user_id
--   - Permissions: EXECUTE revoked from PUBLIC and anon; granted to service_role and authenticated
--
-- Model & Dimension:
--   - Model: gemini-embedding-2
--   - Dimension: 768
--
-- Instructions:
--   - Run this migration script in the Supabase SQL Editor.
-- ============================================================================

CREATE OR REPLACE FUNCTION match_receipts (
  query_embedding vector(768),
  match_user_id uuid,
  match_count int DEFAULT 5,
  filter_year int DEFAULT NULL,
  filter_month int DEFAULT NULL,
  filter_category text DEFAULT NULL,
  filter_currency text DEFAULT NULL
)
RETURNS TABLE (
  receipt_id uuid,
  merchant_name text,
  category text,
  purchase_date date,
  total_amount numeric,
  currency text,
  summary_text text,
  similarity float,
  items json
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
    r.id AS receipt_id,
    r.merchant_name,
    r.category,
    r.purchase_date,
    r.total_amount,
    r.currency,
    re.summary_text,
    ROUND((1 - (re.embedding <=> query_embedding))::numeric, 4)::float AS similarity,
    COALESCE(
      (
        SELECT json_agg(
          json_build_object(
            'item_name', ri.item_name,
            'quantity', ri.quantity,
            'unit_price', ri.unit_price,
            'total_price', ri.total_price
          )
        )
        FROM receipt_items ri
        WHERE ri.receipt_id = r.id
      ),
      '[]'::json
    ) AS items
  FROM receipt_embeddings re
  JOIN receipts r ON r.id = re.receipt_id
  WHERE re.user_id = match_user_id
    AND r.user_id = match_user_id
    AND r.deleted_at IS NULL
    AND (filter_year IS NULL OR EXTRACT(YEAR FROM r.purchase_date) = filter_year)
    AND (filter_month IS NULL OR EXTRACT(MONTH FROM r.purchase_date) = filter_month)
    AND (filter_category IS NULL OR LOWER(r.category) = LOWER(filter_category))
    AND (filter_currency IS NULL OR UPPER(r.currency) = UPPER(filter_currency))
  ORDER BY re.embedding <=> query_embedding ASC
  LIMIT match_count;
END;
$$;

-- ----------------------------------------------------------------------------
-- Permissions & Access Control
-- ----------------------------------------------------------------------------

-- Revoke default public and unauthenticated access
REVOKE EXECUTE ON FUNCTION match_receipts(vector, uuid, int, int, int, text, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION match_receipts(vector, uuid, int, int, int, text, text) FROM anon;

-- Grant execute access only to backend service_role and authenticated users (guarded by auth.uid check)
GRANT EXECUTE ON FUNCTION match_receipts(vector, uuid, int, int, int, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION match_receipts(vector, uuid, int, int, int, text, text) TO authenticated;
