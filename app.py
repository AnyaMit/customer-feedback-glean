from flask import Flask, jsonify
import pandas as pd
from pathlib import Path

app = Flask(__name__)

CSV_PATH = Path("consumer_complaints.csv")

def load_df():
    if not CSV_PATH.exists():
        return pd.DataFrame()
    # read a subset for speed; adjust as needed
    return pd.read_csv(CSV_PATH)

@app.route("/")
def home():
    return "Consumer Complaints API is running. Try /complaints"

@app.route("/complaints")
def complaints():
    df = load_df()
    if df.empty:
        return jsonify({"error": "consumer_complaints.csv not found"}), 404
    # send first 20 rows as JSON
    return jsonify(df.head(20).to_dict(orient="records"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
