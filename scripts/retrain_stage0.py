#!/usr/bin/env python3
"""
Retrain the Stage 0 NLP classifier combining:
1. Base cleaned data (training_data_clean.csv)
2. Synthetic examples to balance classes
3. Active Learning Feedback (training_data_feedback.csv) - Double weighted

Uses Trigrams (ngram_range=(1,3)) as proven in experiments.
Saves to data/stage0_classifier.pkl.
"""

import csv
import random
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

_REPO_ROOT = Path(__file__).parent.parent
_BASE_CSV = _REPO_ROOT / "data" / "training_data_clean.csv"
_FEEDBACK_CSV = _REPO_ROOT / "data" / "training_data_feedback.csv"
_MODEL_OUT = _REPO_ROOT / "data" / "stage0_classifier.pkl"

def generate_synthetic_data():
    techs = ["SQL", "Python", "React", "AWS", "Machine Learning", "Agile", "Scrum", "Jira", "Figma", "Data Analysis", "B2B SaaS", "APIs", "Microservices", "Docker", "Kubernetes"]
    culture_perks = ["health insurance", "dental and vision", "401k match", "unlimited PTO", "flexible working hours", "remote work options", "parental leave", "gym stipend", "learning and development budget", "work life balance"]
    culture_values = ["diversity and inclusion", "collaboration", "innovation", "customer obsession", "bias for action", "ownership", "transparency"]
    
    synthetic = []
    
    # 1000 Preferred
    for _ in range(1000):
        t = random.choice(techs)
        templates = [
            f"Bonus points for experience with {t}",
            f"Familiarity with {t} is a strong plus",
            f"Nice to have: knowledge of {t}",
            f"Ideally, you have shipped products using {t}",
            f"Previous experience with {t} preferred",
            f"A background in {t} would be beneficial",
            f"Experience working with {t} is advantageous"
        ]
        synthetic.append({"text": random.choice(templates), "label": "preferred"})
        
    # 500 Culture
    for _ in range(500):
        p = random.choice(culture_perks)
        v = random.choice(culture_values)
        templates = [
            f"We offer comprehensive {p} for all employees.",
            f"Competitive benefits package including {p}.",
            f"Our culture is built on {v}.",
            f"We strongly believe in {v} and it drives our decisions.",
            f"Enjoy {p} as part of our commitment to {v}.",
            f"Join a team that values {v} above all else.",
            f"We prioritize {v} to ensure a healthy work environment."
        ]
        synthetic.append({"text": random.choice(templates), "label": "culture"})
        
    return synthetic

def main():
    texts = []
    labels = []
    
    # 1. Load base data
    if _BASE_CSV.exists():
        with open(_BASE_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                texts.append(row["text"])
                labels.append(row["label"])
        print(f"Loaded {len(texts)} base examples.")
                
    # 2. Add synthetic data
    synth_data = generate_synthetic_data()
    for row in synth_data:
        texts.append(row["text"])
        labels.append(row["label"])
    print(f"Added {len(synth_data)} synthetic examples.")
        
    # 3. Add Feedback loop data (give it double weight by appending it twice)
    feedback_count = 0
    if _FEEDBACK_CSV.exists():
        with open(_FEEDBACK_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                texts.extend([row["text"], row["text"]])
                labels.extend([row["label"], row["label"]])
                feedback_count += 1
        print(f"Added {feedback_count} feedback loop examples (double weighted).")
        
    print(f"Total training dataset size: {len(texts)}")
    
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print("Training NLP Pipeline with Trigrams...")
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 3),
            max_df=0.9,
            min_df=2
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
    
    print(f"Saving model to {_MODEL_OUT.name}...")
    joblib.dump(pipeline, _MODEL_OUT)
    print("Retraining complete. The Stage 0 pipeline will now use the updated model.")

if __name__ == "__main__":
    main()
