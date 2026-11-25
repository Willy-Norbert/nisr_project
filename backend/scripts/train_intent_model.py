"""Train Analiza's question classifier and report its accuracy.

Run from backend/:  python -m scripts.train_intent_model
"""

from collections import Counter
from datetime import datetime, timezone

import sklearn
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

from app.nlp import entities, intent_model, training_data


def main() -> None:
    texts, labels = training_data.dataset()
    print(f"Training examples: {len(texts)} ({len(training_data.EXAMPLES)} intents)")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)
    scores = cross_val_score(intent_model.build(), texts, labels, cv=cv, scoring="accuracy")
    print(f"5-fold cross-validation accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")

    model = intent_model.train()

    questions = [q for q, _ in training_data.EVALUATION]
    expected = [label for _, label in training_data.EVALUATION]
    masked = [entities.extract(q).masked for q in questions]
    predicted = list(model.predict(masked))
    accuracy = accuracy_score(expected, predicted)
    macro_f1 = f1_score(expected, predicted, average="macro")
    print(f"Hand-written test questions: {len(questions)} | accuracy {accuracy:.3f} | macro F1 {macro_f1:.3f}")
    for q, m, e, p in zip(questions, masked, expected, predicted):
        if e != p:
            print(f"  MISS  {q!r} -> masked {m!r}: expected {e}, got {p}")

    intent_model.save(model, {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "algorithm": "TF-IDF (char 2-5 + word 1-2 n-grams) + logistic regression",
        "scikit_learn": sklearn.__version__,
        "intents": len(training_data.EXAMPLES),
        "training_examples": len(texts),
        "examples_per_intent": dict(Counter(labels)),
        "cross_validation_accuracy": round(float(scores.mean()), 3),
        "test_questions": len(questions),
        "test_accuracy": round(float(accuracy), 3),
        "test_macro_f1": round(float(macro_f1), 3),
    })
    print(f"Saved {intent_model.MODEL_PATH.name} and {intent_model.METRICS_PATH.name}")


if __name__ == "__main__":
    main()
