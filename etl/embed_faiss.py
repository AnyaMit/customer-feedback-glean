import os, math, uuid, json, psycopg, pandas as pd
from psycopg.rows import dict_row
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import faiss

PG_DSN = os.getenv("PG_DSN", "postgresql://user:password@localhost:5433/customer_feedback")
MODEL  = os.getenv("EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH  = int(os.getenv("EMB_BATCH", "256"))
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "800"))
OVERLAP     = int(os.getenv("CHUNK_OVERLAP", "120"))

OUT_DIR = "artifacts"; os.makedirs(OUT_DIR, exist_ok=True)
INDEX_PATH = os.path.join(OUT_DIR, "faiss.index")
META_PATH  = os.path.join(OUT_DIR, "meta.parquet")

def chunk(text, size=CHUNK_CHARS, overlap=OVERLAP):
    if not text: return []
    s = 0; n = len(text); out = []
    while s < n:
        e = min(n, s + size)
        out.append(text[s:e])
        if e == n: break
        s = e - overlap
        if s < 0: s = 0
    return out

def main():
    print("Loading model:", MODEL)
    model = SentenceTransformer(MODEL)  # CPU by default

    # Count rows for progress
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM gold.rag_source_textual")
        total_rows = cur.fetchone()[0]
    print(f"Rows to process: {total_rows}")

    ids, vecs, meta_rows = [], [], []
    with psycopg.connect(PG_DSN) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""SELECT feedback_key, feedback_id, created_at, company, product, issue, body
                       FROM gold.rag_source_textual
                       ORDER BY created_at DESC""")

        buf_texts, buf_meta = [], []
        pbar = tqdm(total=total_rows, desc="Embedding rows", unit="row")
        for row in cur:
            text = row["body"]
            chunks = chunk(text)
            for idx, ch in enumerate(chunks):
                buf_texts.append(ch)
                buf_meta.append({
                    "doc_id": row["feedback_key"],
                    "feedback_id": row["feedback_id"],
                    "created_at": row["created_at"],
                    "company": row["company"],
                    "product": row["product"],
                    "issue": row["issue"],
                    "chunk_id": idx,
                    "chunk_chars": len(ch),
                })
                if len(buf_texts) >= BATCH:
                    embs = model.encode(buf_texts, normalize_embeddings=True, show_progress_bar=False)
                    vecs.extend(embs.astype("float32"))
                    meta_rows.extend(buf_meta)
                    buf_texts.clear(); buf_meta.clear()
            pbar.update(1)
        pbar.close()

        # flush tail
        if buf_texts:
            embs = model.encode(buf_texts, normalize_embeddings=True, show_progress_bar=False)
            vecs.extend(embs.astype("float32"))
            meta_rows.extend(buf_meta)

    import numpy as np
    if not vecs:
        print("No embeddings produced."); return
    mat = np.vstack(vecs).astype("float32")
    dim = mat.shape[1]
    index = faiss.IndexFlatIP(dim)  # cosine because we normalized vectors
    index.add(mat)
    faiss.write_index(index, INDEX_PATH)
    pd.DataFrame(meta_rows).to_parquet(META_PATH, index=False)
    print(f"Saved index: {INDEX_PATH}  vectors={index.ntotal}")
    print(f"Saved metadata: {META_PATH}")

if __name__ == "__main__":
    main()
