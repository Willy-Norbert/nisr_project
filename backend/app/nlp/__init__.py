"""Analiza's own natural-language layer for the Ask page: no external AI service.

- entities.py       finds crops, districts, provinces, indicators, periods (typo-tolerant, EN/RW/FR)
- training_data.py  labelled example questions used to train the intent model
- intent_model.py   TF-IDF + logistic regression question classifier (scikit-learn)
"""
