"""Analiza's question classifier: TF-IDF (character + word n-grams) -> logistic regression (scikit-learn).

Character n-grams make it robust to typos and to Kinyarwanda/French word forms; word n-grams capture phrasing.
Entities are masked before classification (see entities.py), so the model generalises to every crop and district.

The trained model is saved next to this file. If it cannot be loaded (missing file, different scikit-learn version)
it is retrained in memory from training_data.py, which takes about a second.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app.nlp import training_data

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).with_name("intent_model.joblib")
METRICS_PATH = Path(__file__).with_name("intent_metrics.json")


def build() -> Pipeline:
    features = FeatureUnion([
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=1)),
        ("words", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b",
                                  sublinear_tf=True)),
    ])
    classifier = LogisticRegression(C=8.0, max_iter=3000, class_weight="balanced")
    return Pipeline([("features", features), ("classifier", classifier)])


def train() -> Pipeline:
    texts, labels = training_data.dataset()
    model = build()
    model.fit(texts, labels)
    return model


@lru_cache
def model() -> Pipeline:
    try:
        saved = joblib.load(MODEL_PATH)
        if saved.get("sklearn") == sklearn.__version__:
            return saved["model"]
        logger.info("Intent model saved with scikit-learn %s, running %s: retraining", saved.get("sklearn"),
                    sklearn.__version__)
    except (OSError, EOFError, KeyError, AttributeError, ValueError, ImportError) as exc:
        logger.info("Intent model not loaded (%s): retraining", exc)
    return train()


def predict(masked_text: str) -> tuple[str, float, list[tuple[str, float]]]:
    """Return (best intent, its probability, top-3 alternatives)."""
    m = model()
    probabilities = m.predict_proba([masked_text])[0]
    ranked = sorted(zip(m.classes_, probabilities), key=lambda x: x[1], reverse=True)
    return ranked[0][0], float(ranked[0][1]), [(c, round(float(p), 3)) for c, p in ranked[:3]]


def metrics() -> dict:
    try:
        return json.loads(METRICS_PATH.read_text())
    except (OSError, ValueError):
        return {}


def save(model_: Pipeline, metrics_: dict) -> None:
    joblib.dump({"model": model_, "sklearn": sklearn.__version__}, MODEL_PATH, compress=3)
    METRICS_PATH.write_text(json.dumps(metrics_, indent=2))
