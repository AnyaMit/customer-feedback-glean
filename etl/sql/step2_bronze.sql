-- === AUDIT ===
CREATE SCHEMA IF NOT EXISTS util;

CREATE TABLE IF NOT EXISTS util.load_audit (
  load_id         uuid PRIMARY KEY,
  source_path     text NOT NULL,
  started_at      timestamptz NOT NULL DEFAULT now(),
  finished_at     timestamptz,
  rowcount_in     bigint,
  rowcount_bronze bigint,
  rowcount_silver bigint,
  checksum        text,
  status          text NOT NULL CHECK (status IN ('started','success','error')),
  error           text
);

-- === BRONZE ===
CREATE SCHEMA IF NOT EXISTS bronze;

-- bad rows quarantine
CREATE TABLE IF NOT EXISTS bronze._rejects (
  load_id     uuid NOT NULL,
  raw_record  jsonb NOT NULL,
  reason      text  NOT NULL,
  rejected_at timestamptz NOT NULL DEFAULT now()
);

-- raw landing table (as raw as possible + a few convenience cols)
CREATE TABLE IF NOT EXISTS bronze.feedback_raw (
  load_id      uuid NOT NULL,
  row_num      bigint NOT NULL,
  source_file  text NOT NULL,
  ingested_at  timestamptz NOT NULL DEFAULT now(),
  payload      jsonb NOT NULL,

  -- optional convenience columns (nullable)
  feedback_id  text,
  created_at   timestamptz,
  user_id      text,
  channel      text,
  rating       numeric,
  text         text
);

CREATE INDEX IF NOT EXISTS ix_feedback_raw_load ON bronze.feedback_raw(load_id);
CREATE INDEX IF NOT EXISTS ix_feedback_raw_created ON bronze.feedback_raw(created_at);

-- === SILVER (minimal for now; populated in Step 3) ===
CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.feedback (
  feedback_key  text PRIMARY KEY,      -- deterministic hash
  feedback_id   text,
  created_at    timestamptz NOT NULL,
  user_id       text,
  channel       text,
  rating        numeric,
  text          text NOT NULL,
  first_seen_at timestamptz NOT NULL,
  last_seen_at  timestamptz NOT NULL,
  load_id       uuid NOT NULL
);

-- === GOLD convenience views (we'll use after we load some data) ===
CREATE SCHEMA IF NOT EXISTS gold;

CREATE OR REPLACE VIEW gold.feedback_daily_counts AS
SELECT date_trunc('day', created_at) AS day, count(*) AS feedback_count
FROM silver.feedback
GROUP BY 1
ORDER BY 1;

CREATE OR REPLACE VIEW gold.rating_distribution AS
SELECT rating, count(*) AS n
FROM silver.feedback
GROUP BY 1
ORDER BY 1;
