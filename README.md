# Customer Feedback Glean

This project builds a **data pipeline and vector search system** for analyzing consumer complaint data.  
It uses a **Medallion architecture** (Bronze → Silver → Gold) with PostgreSQL, Docker, and FAISS for vector indexing.

---

## 🚀 Features
- Ingests raw **CSV complaint data** into PostgreSQL (Bronze layer).
- Cleans and structures textual and non-textual feedback (Silver layer).
- Aggregates and exposes insights (Gold layer).
- Generates **embeddings with SentenceTransformers**.
- Stores and queries vectors using **FAISS** for similarity search.

---

## 📦 Tech Stack
- **Python 3.10+**
- **Docker & docker-compose**
- **PostgreSQL**
- **FAISS**
- **SentenceTransformers**
- **Pandas**

---

## 🔧 Quickstart
1. Clone the repo:
   \`\`\`bash
   git clone https://github.com/AnyaMit/customer-feedback-glean.git
   cd customer-feedback-glean
   \`\`\`

2. Create & activate a virtual environment:
   \`\`\`bash
   python -m venv .venv
   source .venv/bin/activate
   \`\`\`

3. Install dependencies:
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

4. Run the pipeline (see [Instructions.md](Instructions.md) for full details).

---

## 📖 Detailed Setup
For step-by-step instructions (including ETL, embeddings, and FAISS indexing),  
see [**Instructions.md**](Instructions.md).

---

## 🤝 Contributing
- Fork the repo and submit a PR with clear commit messages.
- Please keep large data and virtual environments **out of Git** (see .gitignore).

---

## 📜 License
MIT License

