import os, csv, uuid, hashlib, json, datetime, time
from typing import Dict, Any, List, Tuple
import psycopg
from psycopg.rows import dict_row
import yaml
from tqdm import tqdm

PG_DSN = os.getenv("PG_DSN", "postgresql://user:password@localhost:5433/customer_feedback")
CSV_PATH = os.getenv("CSV_PATH", "data/raw/complaints.csv")
CONTRACT_PATH = os.getenv("CONTRACT_PATH", "etl/config/contract.yml")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))

SYNTH_FIELDS = ["Product","Sub-product","Issue","Sub-issue","Company","State","Submitted via"]

def read_contract():
    with open(CONTRACT_PATH, "r") as f:
        return yaml.safe_load(f)

def checksum_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def header_map(csv_header: List[str], contract: Dict[str, Any]) -> Dict[str, str]:
    m = {}
    header_lc = [h.strip().lower() for h in csv_header]
    for canonical, candidates in contract["columns"].items():
        hit = None
        for c in candidates:
            if c.lower() in header_lc:
                hit = csv_header[header_lc.index(c.lower())]
                break
        m[canonical] = hit
    return m

def parse_datetime(s: str):
    s = (s or "").strip()
    if not s: return None
    fmts = ["%Y-%m-%d %H:%M:%S","%Y-%m-%d","%m/%d/%Y %H:%M","%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%S","%Y-%m-%dT%H:%M:%S.%f","%Y-%m-%dT%H:%M:%S.%fZ"]
    for fmt in fmts:
        try:
            s2 = s.replace("Z","")
            return datetime.datetime.strptime(s2, fmt)
        except Exception:
            pass
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None

def coerce_types(row: Dict[str, Any], mapping: Dict[str, str], rules: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    errors, out = [], {}
    for canonical, actual in mapping.items():
        val = row.get(actual) if actual else None
        if canonical == "created_at" and val is not None:
            dt = parse_datetime(str(val))
            if not dt: errors.append("created_at_parse_fail")
            out["created_at"] = dt
        elif canonical == "rating" and val not in (None, ""):
            try: out["rating"] = float(val)
            except Exception: out["rating"] = None
        else:
            out[canonical] = val if val not in ("", None) else None
    for req in rules.get("required", []):
        if out.get(req) in (None, ""): errors.append(f"required_missing:{req}")
    return out, errors

def synthesize_text_from_row(row: dict) -> str:
    parts = []
    for k in SYNTH_FIELDS:
        v = row.get(k)
        if v not in (None, ""): parts.append(f"{k}={v}")
    return ", ".join(parts) if parts else None

def main():
    contract = read_contract(); rules = contract["rules"]
    load_id = uuid.uuid4(); source_path = os.path.abspath(CSV_PATH); ck = checksum_file(source_path)

    total_rows = sum(1 for _ in open(source_path, encoding="utf-8")) - 1

    start = time.time()
    rowcount_in = 0; rowcount_bronze = 0; rejects = 0

    with psycopg.connect(PG_DSN, autocommit=False) as conn, conn.cursor(row_factory=dict_row) as cur:
        # speed tweak: acceptable for bulk load (turns off per-stmt fsync)
        cur.execute("SET LOCAL synchronous_commit = OFF;")

        # audit start
        cur.execute(
            "INSERT INTO util.load_audit(load_id, source_path, checksum, status) VALUES (%s,%s,%s,'started')",
            (load_id, source_path, ck)
        )
        conn.commit()

        insert_sql = """
            INSERT INTO bronze.feedback_raw
              (load_id,row_num,source_file,payload,feedback_id,created_at,user_id,channel,rating,text)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        batch = []
        with open(source_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            mapping = header_map(reader.fieldnames, contract)

            for i, row in enumerate(tqdm(reader, desc="Bronze load", unit="rows", total=total_rows, mininterval=1), start=1):
                rowcount_in += 1
                coerced, errs = coerce_types(row, mapping, rules)

                has_text = bool(coerced.get("text") and str(coerced["text"]).strip())
                synthetic_summary = None if has_text else synthesize_text_from_row(row)
                row["_has_text"] = has_text
                if synthetic_summary: row["_synthetic_text"] = synthetic_summary
                if not coerced.get("created_at"): coerced["created_at"] = datetime.datetime.now()

                if errs:
                    cur.execute("INSERT INTO bronze._rejects(load_id, raw_record, reason) VALUES (%s,%s,%s)",
                                (load_id, json.dumps(row), ",".join(errs)))
                    rejects += 1
                    continue

                batch.append((
                    str(load_id), i, source_path, json.dumps(row),
                    coerced.get("feedback_id"),
                    coerced.get("created_at"),
                    coerced.get("user_id"),
                    coerced.get("channel"),
                    coerced.get("rating"),
                    coerced.get("text")
                ))

                if len(batch) >= BATCH_SIZE:
                    cur.executemany(insert_sql, batch)  # psycopg3-native
                    conn.commit()
                    rowcount_bronze += len(batch)
                    batch.clear()

            if batch:
                cur.executemany(insert_sql, batch)
                conn.commit()
                rowcount_bronze += len(batch)

        # finalize audit
        with psycopg.connect(PG_DSN) as conn2, conn2.cursor(row_factory=dict_row) as cur2:
            cur2.execute("SELECT COUNT(*) AS c FROM bronze.feedback_raw WHERE load_id = %s", (load_id,))
            rowcount_b = cur2.fetchone()["c"]
            cur2.execute("""
                UPDATE util.load_audit
                SET finished_at = now(),
                    rowcount_in = %s,
                    rowcount_bronze = %s,
                    status = 'success'
                WHERE load_id = %s
            """, (rowcount_in, rowcount_b, load_id))
            conn2.commit()

    elapsed = time.time() - start
    print(f"Load {load_id} complete. In={rowcount_in} Bronze={rowcount_bronze} Rejects={rejects} Time={elapsed:.1f}s (batch={BATCH_SIZE})")

if __name__ == "__main__":
    main()
