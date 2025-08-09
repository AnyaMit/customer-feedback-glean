# Customer Feedback Glean
*Glean recurring themes and actionable insights from customer feedback with emerging and established technologies.*

## Project North Star
Give anyone — regardless of budget — the power to load any set of customer feedback, find similar cases, cluster recurring themes, and surface patterns worth acting on.
Built **free-first** for maximum accessibility, with optional paid APIs for when the results clearly justify the cost.

## Goals
- **Project outcome:** Local, free stack that:
  - Finds similar feedback items via RAG
  - Clusters & names themes
  - Summarizes key findings locally
- **Evidence:**
  - Demo UI
  - Latency <3s/query
  - Top-3 relevance judged “good” on 10 seed queries
- **Education:** Show *when* paid APIs meaningfully improve results.

## Non-Goals
- Multi-tenant SaaS
- Advanced MLOps or fine-tuning
- Proprietary data ingestion

## 🛠 Tools & Installation (M3 Mac – Free-First Setup)
This project is designed to run **100% locally** on an Apple Silicon M3 Mac using free tools. No API keys or paid services are required to get started.
We support both **Ollama models** and **get-oss models** for maximum flexibility. Paid APIs are optional and can be enabled later.

### 1. Prerequisites
| Tool | Purpose | Install Command / Link |
|------|---------|------------------------|
| **Python 3.11+** | Core runtime | [Download](https://www.python.org/downloads/) or `brew install python@3.11` |
| **pip** | Package manager | Comes with Python |
| **Ollama** | Local LLM runtime | [Install](https://ollama.com/download) |
| **get-oss models** | Open-source LLMs | [Guide](https://github.com/get-oss/) |
| **Docker Desktop** *(optional)* | Containerized vector DBs | [Install](https://www.docker.com/products/docker-desktop/) |
| **Git** | Version control | `brew install git` |

### 2. Clone the Repository
```bash
git clone https://github.com/<your-org>/customer-feedback-glean.git
cd customer-feedback-glean
```

### 3. Set Up Python Environment
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Your Stack
Every script starts with a **Your Setup** block:
```python
# ===== YOUR SETUP =====
STACK = "local"  # local | hybrid | paid
EMBEDDING_PROVIDER = "sentence-transformers"  # or "ollama" or "get-oss"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
SUMMARIZER_PROVIDER = "ollama"  # or "get-oss" or "openai"
SUMMARIZER_MODEL = "oss-20b"
DATASET_PATH = "data/raw/sample_feedback.csv"
# ======================
```
💡 Adjust for your installed tools & models — no other code changes needed.

### 5. Pull Models
```bash
# Ollama summarization model
ollama pull oss-20b

# Optional embeddings
ollama pull nomic-embed-text

# If using get-oss
get-oss pull <model-name>
```

### 6. First Run
```bash
make ingest
make embed
make cluster
make ui
```
Opens UI at [http://localhost:8501](http://localhost:8501).

### 7. Verify Setup
```bash
make test
```

## Architecture Overview
1. **Ingest:** Load + normalize dataset (CSV/JSON → parquet)
2. **Embed:** Create vector store (FAISS local by default)
3. **Approach 1 – Rapid RAG:** Nearest neighbor search + summary
4. **Approach 2 – Categorize & Trend:** Cluster embeddings, label top themes, show frequency over time
5. **Approach 3 – Severity/Signals (optional):** Rule-based tagging
6. **Eval Framework:** Measure latency, top-3 relevance, cluster coverage, and drift

## Evaluation Framework
- **Latency:** ms/query
- **Top-3 relevance:** Manual yes/no across 10 seed queries
- **Cluster coverage:** % assigned to top N clusters
- **Drift:** Weekly changes in top themes
- **Free vs Paid delta:** Compare metrics before/after API use

