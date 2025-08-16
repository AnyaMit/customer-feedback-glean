import os, uuid, hashlib, time
import psycopg
from psycopg.rows import dict_row

PG_DSN   = os.getenv("PG_DSN", "postgresql://user:password@localhost:5433/customer_feedback")
CSV_PATH = os.getenv("CSV_PATH", "data/raw/complaints.csv")

# Columns in the exact CSV order (all text for fast ingest)
STG_COLS = [
  "date_received","product","sub_product","issue","sub_issue",
  "consumer_complaint_narrative","company_public_response","company","state",
  "zip_code","tags","consumer_consent_provided","submitted_via","date_sent_to_company",
  "company_response_to_consumer","timely_response","consumer_disputed","complaint_id"
]

DDL = f"""
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE TABLE IF NOT EXISTS bronze.stg_complaints_raw (
  {", ".join([f"{c} text" for c in STG_COLS])}
);
"""

INSERT_BRONZE = """
INSERT INTO bronze.feedback_raw
  (load_id,row_num,source_file,payload,feedback_id,created_at,user_id,channel,rating,text)
SELECT
  %(load_id)s,
  ROW_NUMBER() OVER () AS row_num,
  %(source_file)s,
  to_jsonb(s) AS payload,
  NULLIF(s.complaint_id,'') AS feedback_id,
  NULLIF(s.date_received,'')::date::timestamp AS created_at,
  NULLIF(s.zip_code,'') AS user_id,
  NULLIF(s.submitted_via,'') AS channel,
  NULL::numeric AS rating,
  NULLIF(s.consumer_complaint_narrative,'') AS text
FROM bronze.stg_complaints_raw s;
"""

def sha256_file(path):
    import hashlib
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    source_path = os.path.abspath(CSV_PATH)
    load_id = str(uuid.uuid4())
    checksum = sha256_file(source_path)
    t0 = time.time()

    with psycopg.connect(PG_DSN, autocommit=True) as conn, conn.cursor(row_factory=dict_row) as cur:
        # audit start
        cur.execute("""
            INSERT INTO util.load_audit(load_id, source_path, checksum, status)
            VALUES (%s,%s,%s,'started')
        """, (load_id, source_path, checksum))

        # staging table (idempotent) and truncate
        cur.execute(DDL)
        cur.execute("TRUNCATE TABLE bronze.stg_complaints_raw;")

        # fast COPY by column order (HEADER just skips the first line)
        with open(source_path, "r", encoding="utf-8", newline="") as f:
            cur.copy("""
                COPY bronze.stg_complaints_raw
                FROM STDIN WITH (FORMAT csv, HEADER true)
            """, f)

        # speed tweak for set-based insert
        cur.execute("SET LOCAL synchronous_commit = OFF;")
        cur.execute(INSERT_BRONZE, {"load_id": load_id, "source_file": source_path})

        # finalize audit
        cur.execute("SELECT COUNT(*) AS c FROM bronze.feedback_raw WHERE load_id = %s", (load_id,))
        c = cur.fetchone()["c"]
        cur.execute("""
            UPDATE util.load_audit
            SET finished_at = now(),
                rowcount_in = %s,
                rowcount_bronze = %s,
                status = 'success'
            WHERE load_id = %s
        """, (c, c, load_id))

    print(f"COPY load {load_id} complete. Bronze={c} Time={time.time()-t0:.1f}s")

if __name__ == "__main__":
    main()
