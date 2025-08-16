-- Silver tables (idempotent)
CREATE TABLE IF NOT EXISTS silver.feedback_textual (
  feedback_key  text PRIMARY KEY,
  feedback_id   text,
  created_at    timestamptz NOT NULL,
  user_id       text,
  channel       text,
  rating        numeric,
  text          text NOT NULL,
  company       text,
  product       text,
  issue         text,
  first_seen_at timestamptz NOT NULL,
  last_seen_at  timestamptz NOT NULL,
  load_id       uuid NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.feedback_nontextual (
  feedback_key       text PRIMARY KEY,
  feedback_id        text,
  created_at         timestamptz NOT NULL,
  user_id            text,
  channel            text,
  company            text,
  product            text,
  issue              text,
  synthetic_summary  text,
  first_seen_at      timestamptz NOT NULL,
  last_seen_at       timestamptz NOT NULL,
  load_id            uuid NOT NULL
);

-- TEXTUAL (has narrative)
WITH last_load AS (
  SELECT load_id
  FROM util.load_audit
  WHERE status = 'success'
  ORDER BY started_at DESC
  LIMIT 1
),
bronze_rows AS (
  SELECT br.*
  FROM bronze.feedback_raw br
  WHERE br.load_id = (SELECT load_id FROM last_load)
),
textual AS (
  SELECT
    encode(digest(
      coalesce(br.text,'') || '|' ||
      coalesce(br.created_at::text,'') || '|' ||
      coalesce(br.user_id,'') || '|' ||
      coalesce(br.feedback_id,'') || '|' ||
      coalesce((br.payload->>'Company'), '')
    , 'sha256'), 'hex')              AS feedback_key,
    br.feedback_id,
    br.created_at,
    br.user_id,
    br.channel,
    br.rating,
    br.text,
    br.payload->>'Company'           AS company,
    coalesce(br.payload->>'Product', br.payload->>'Sub-product') AS product,
    coalesce(br.payload->>'Issue', br.payload->>'Sub-issue')     AS issue,
    now() AS first_seen_at,
    now() AS last_seen_at,
    br.load_id
  FROM bronze_rows br
  WHERE br.text IS NOT NULL AND length(trim(br.text)) > 0
)
INSERT INTO silver.feedback_textual (
  feedback_key, feedback_id, created_at, user_id, channel, rating, text,
  company, product, issue, first_seen_at, last_seen_at, load_id
)
SELECT
  feedback_key, feedback_id, created_at, user_id, channel, rating, text,
  company, product, issue, first_seen_at, last_seen_at, load_id
FROM textual
ON CONFLICT (feedback_key) DO UPDATE
SET last_seen_at = EXCLUDED.last_seen_at,
    rating = COALESCE(EXCLUDED.rating, silver.feedback_textual.rating),
    channel = COALESCE(EXCLUDED.channel, silver.feedback_textual.channel),
    text = COALESCE(EXCLUDED.text, silver.feedback_textual.text);

-- NONTEXTUAL (no narrative) – use subquery so scope is self-contained
INSERT INTO silver.feedback_nontextual (
  feedback_key, feedback_id, created_at, user_id, channel, company, product, issue,
  synthetic_summary, first_seen_at, last_seen_at, load_id
)
SELECT * FROM (
  WITH last_load AS (
    SELECT load_id
    FROM util.load_audit
    WHERE status = 'success'
    ORDER BY started_at DESC
    LIMIT 1
  ),
  bronze_rows AS (
    SELECT br.*
    FROM bronze.feedback_raw br
    WHERE br.load_id = (SELECT load_id FROM last_load)
  )
  SELECT
    encode(digest(
      coalesce(br.created_at::text,'') || '|' ||
      coalesce(br.user_id,'') || '|' ||
      coalesce(br.feedback_id,'') || '|' ||
      coalesce((br.payload->>'Company'), '') || '|' ||
      coalesce((br.payload->>'Product'), '')
    , 'sha256'), 'hex')              AS feedback_key,
    br.feedback_id,
    br.created_at,
    br.user_id,
    br.channel,
    br.payload->>'Company'           AS company,
    coalesce(br.payload->>'Product', br.payload->>'Sub-product') AS product,
    coalesce(br.payload->>'Issue', br.payload->>'Sub-issue')     AS issue,
    br.payload->>'_synthetic_text'   AS synthetic_summary,
    now() AS first_seen_at,
    now() AS last_seen_at,
    br.load_id
  FROM bronze_rows br
  WHERE (br.text IS NULL OR length(trim(br.text)) = 0)
) AS nontextual_src
ON CONFLICT (feedback_key) DO UPDATE
SET last_seen_at = EXCLUDED.last_seen_at,
    channel = COALESCE(EXCLUDED.channel, silver.feedback_nontextual.channel),
    synthetic_summary = COALESCE(EXCLUDED.synthetic_summary, silver.feedback_nontextual.synthetic_summary);
