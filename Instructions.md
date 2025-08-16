Instructions

This project implements a medallion architecture (bronze → silver → gold) for customer feedback data, followed by embedding + FAISS indexing for retrieval.

1. Setup
Clone & Environment
git clone <your-repo-url>
cd customer-feedback-glean
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

Docker

Start Postgres via docker-compose:

docker compose up -d

2. Bronze: Load Raw Data
Load CSV into Staging
cat data/raw/complaints.csv | \
docker compose exec -e PGPASSWORD=password -T db \
psql -U user -d customer_feedback -v ON_ERROR_STOP=1 \
-c "\copy bronze.stg_complaints_raw FROM STDIN WITH (FORMAT csv, HEADER true)"


Check row count:

docker compose exec -e PGPASSWORD=password -T db \
psql -U user -d customer_feedback \
-c "SELECT COUNT(*) FROM bronze.stg_complaints_raw;"

3. Silver: Transform Data
Split Textual / Nontextual
cat etl/sql/step4_silver_split.sql | \
docker compose exec -e PGPASSWORD=password -T db \
psql -U user -d customer_feedback -v ON_ERROR_STOP=1 -f -


Check counts:

docker compose exec -e PGPASSWORD=password -T db \
psql -U user -d customer_feedback \
-c "SELECT COUNT(*) FROM silver.feedback_textual;"

4. Gold: Aggregations

Run gold layer SQL:

cat etl/sql/step5_gold_views.sql | \
docker compose exec -e PGPASSWORD=password -T db \
psql -U user -d customer_feedback -v ON_ERROR_STOP=1 -f -


Example check:

docker compose exec -e PGPASSWORD=password -T db \
psql -U user -d customer_feedback \
-c "SELECT * FROM gold.daily_product_counts ORDER BY day DESC LIMIT 10;"

5. Embeddings + FAISS
Install deps
pip install sentence-transformers faiss-cpu

Run Embedding Script
CSV_PATH="data/raw/complaints.csv" python etl/embed_faiss.py


You should see progress like:

416962/416962 [33:43<00:00, 206.09row/s]
Saved index: artifacts/faiss.index  vectors=778022
Saved metadata: artifacts/meta.parquet

6. Repo Hygiene
Add Instructions File
git add Instructions.md
git commit -m "Add Instructions.md with setup + ETL steps"
git push origin main
