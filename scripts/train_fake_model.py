"""Train the fake job detector (the only model in this project that needs training).

Data
  1. EMSCAD (Employment Scam Aegean Dataset): 17,880 real job ads, 866 of them fake.
     Download fake_job_postings.csv from Kaggle and put it in the data folder:
     https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction
  2. data/india_scam_examples.json: 240 Indian-style ads (120 genuine, 120 scams with
     registration fees, UPI, WhatsApp, Aadhaar...). EMSCAD is US data from 2012-14 and
     does not know these patterns, so we add them.

Model
  Text = title + description + requirements + benefits (only fields every job in our app has;
  'company_profile' is NOT used because our collected jobs never have it, which would bias the model).
  Features = word 1-2 grams + character 3-5 grams (TF-IDF). Classifier = Logistic Regression with
  class_weight='balanced' because only ~5% of ads are fake.

Evaluation
  80/20 split, stratified. The test set is never used for training or for choosing the threshold.

Run:  python scripts/train_fake_model.py
Writes models/fake_job_model.joblib and models/fake_model_report.json
"""
import json
import re

import _path  # noqa: F401
import joblib
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

import config

CSV = config.DATA_DIR / "fake_job_postings.csv"
INDIA = config.DATA_DIR / "india_scam_examples.json"
THRESHOLD = 0.55          # probability above which the model calls an ad fake (chosen by cross-validation)
REPORT = config.MODEL_DIR / "fake_model_report.json"


def clean(text):
    return re.sub(r"\s+", " ", BeautifulSoup(text, "html.parser").get_text(" ")) if "<" in text else text


def build_model():
    features = FeatureUnion([
        ("words", TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2, max_features=60000, sublinear_tf=True)),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_features=60000, sublinear_tf=True)),
    ])
    return Pipeline([("features", features), ("clf", LogisticRegression(max_iter=3000, class_weight="balanced", C=4))])


def scores(y_true, prob):
    pred = prob >= THRESHOLD
    p, r, f1, _ = precision_recall_fscore_support(y_true, pred, average="binary", zero_division=0)
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3),
            "roc_auc": round(roc_auc_score(y_true, prob), 3), "confusion_matrix": confusion_matrix(y_true, pred).tolist()}


if __name__ == "__main__":
    if not CSV.exists():
        raise SystemExit(f"Put fake_job_postings.csv in {config.DATA_DIR} first (see the instructions at the top).")
    df = pd.read_csv(CSV).fillna("")
    text = (df["title"] + ". " + df["description"] + " " + df["requirements"] + " " + df["benefits"]).map(clean).values
    y = df["fraudulent"].astype(int).values
    india = json.loads(INDIA.read_text(encoding="utf-8")) if INDIA.exists() else []
    i_text = np.array([r["text"] for r in india]); i_y = np.array([r["fake"] for r in india])
    print(f"EMSCAD: {len(y)} ads, {y.sum()} fake ({100 * y.mean():.1f}%).  Indian examples: {len(i_y)}")

    X_tr, X_te, y_tr, y_te = train_test_split(text, y, test_size=0.2, stratify=y, random_state=42)
    report = {"threshold": THRESHOLD}
    if len(i_y):
        i_tr, i_te = train_test_split(np.arange(len(i_y)), test_size=0.5, stratify=i_y, random_state=3)
        X_tr, y_tr = np.concatenate([X_tr, i_text[i_tr]]), np.concatenate([y_tr, i_y[i_tr]])
    model = build_model().fit(X_tr, y_tr)
    report["emscad_test"] = scores(y_te, model.predict_proba(X_te)[:, 1])
    print("EMSCAD test set:", report["emscad_test"])
    if len(i_y):
        report["india_test"] = scores(i_y[i_te], model.predict_proba(i_text[i_te])[:, 1])
        print("Indian test set:", report["india_test"])

    # final model: train on everything so the app gets the most knowledge
    final = build_model().fit(np.concatenate([text, i_text]) if len(i_y) else text,
                              np.concatenate([y, i_y]) if len(i_y) else y)
    joblib.dump({"model": final, "threshold": THRESHOLD}, config.FAKE_MODEL_FILE, compress=3)
    REPORT.write_text(json.dumps(report, indent=2))
    print(f"Saved {config.FAKE_MODEL_FILE} and {REPORT}")
