#!/usr/bin/env python3
"""
Train a TF-IDF + Logistic Regression NLP classifier on the cleaned JD data.
Evaluates accuracy and saves the model to data/stage0_classifier.pkl.
"""

import csv
import joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

_REPO_ROOT = Path(__file__).parent.parent
_INPUT_CSV = _REPO_ROOT / "data" / "training_data_clean.csv"
_MODEL_OUT = _REPO_ROOT / "data" / "stage0_classifier.pkl"

def main():
    print(f"Loading data from {_INPUT_CSV.name}...")
    texts = []
    labels = []
    
    with open(_INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row["text"])
            labels.append(row["label"])
            
    print(f"Loaded {len(texts)} samples.")
    
    # Split into 80% train, 20% test for evaluation
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print("Training model...")
    # Logistic Regression provides well-calibrated probability scores,
    # which is perfect for our Confidence-Based Fallback logic.
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),  # Use words and pairs of words (bigrams)
            max_df=0.9,          # Ignore words that appear in 90%+ of lines
            min_df=2             # Ignore words that appear only once
        )),
        ('clf', LogisticRegression(
            class_weight='balanced',
            random_state=42,
            max_iter=1000
        ))
    ])
    
    pipeline.fit(X_train, y_train)
    
    print("\n--- Evaluation on Test Set ---")
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred))
    
    # Analyze confidence on incorrect predictions
    y_proba = pipeline.predict_proba(X_test)
    classes = pipeline.classes_
    
    print("\n--- Outlier Analysis (Model Mistakes) ---")
    mistakes = 0
    for i in range(len(X_test)):
        if y_test[i] != y_pred[i]:
            mistakes += 1
            if mistakes <= 5: # Just show a few examples
                # Get the probability of the predicted class
                pred_idx = list(classes).index(y_pred[i])
                confidence = y_proba[i][pred_idx] * 100
                
                print(f"[{mistakes}] TEXT: {X_test[i].encode('ascii', 'replace').decode('ascii')}")
                print(f"    TRUE: {y_test[i]} | PREDICTED: {y_pred[i]} ({confidence:.1f}% confidence)\n")
    
    print(f"Total mistakes in test set: {mistakes} out of {len(X_test)} samples ({(mistakes/len(X_test))*100:.1f}% error rate)")
    
    print(f"\nSaving model to {_MODEL_OUT.name}...")
    joblib.dump(pipeline, _MODEL_OUT)
    print("Done!")

if __name__ == "__main__":
    main()
