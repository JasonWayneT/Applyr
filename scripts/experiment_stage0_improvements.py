#!/usr/bin/env python3
"""
Experiment to boost Stage 0 NLP Classifier accuracy via:
1. Synthetic Data Augmentation (balancing 'preferred' and 'culture')
2. Trigram vectorization (ngram_range=(1, 3))
3. Demonstrating Header Context impact
"""

import csv
import random
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

_REPO_ROOT = Path(__file__).parent.parent
_INPUT_CSV = _REPO_ROOT / "data" / "training_data_clean.csv"

def generate_synthetic_data():
    """Generate synthetic examples to balance the dataset."""
    techs = ["SQL", "Python", "React", "AWS", "Machine Learning", "Agile", "Scrum", "Jira", "Figma", "Data Analysis", "B2B SaaS", "APIs", "Microservices", "Docker", "Kubernetes"]
    culture_perks = ["health insurance", "dental and vision", "401k match", "unlimited PTO", "flexible working hours", "remote work options", "parental leave", "gym stipend", "learning and development budget", "work life balance"]
    culture_values = ["diversity and inclusion", "collaboration", "innovation", "customer obsession", "bias for action", "ownership", "transparency"]
    
    synthetic = []
    
    # Generate 1000 Preferred
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
        
    # Generate 500 Culture
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
    
    # 1. Load real data
    with open(_INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row["text"])
            labels.append(row["label"])
            
    # 2. Add synthetic data
    synth_data = generate_synthetic_data()
    for row in synth_data:
        texts.append(row["text"])
        labels.append(row["label"])
        
    print(f"Total dataset size: {len(texts)} (Added {len(synth_data)} synthetic examples to balance classes)")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    # 3. Train with Trigrams (1, 3)
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 3),  # Increased from (1, 2)
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
    
    print("\n--- NEW Evaluation on Test Set ---")
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred))
    
    # 4. Demonstrate Header Context Impact
    print("\n--- Header Context Demonstration ---")
    tricky_examples = [
        "SQL and Python",
        "Defining product metrics/instrumentation",
        "Redesign workflows with AI (human-in-loop judgment)"
    ]
    
    headers_to_test = [
        "", 
        "[HEADER] What you must have: ", 
        "[HEADER] Nice to have: "
    ]
    
    classes = pipeline.classes_
    
    for base_text in tricky_examples:
        print(f"\nBase Bullet: '{base_text}'")
        for header in headers_to_test:
            combined_text = f"{header}{base_text}"
            pred = pipeline.predict([combined_text])[0]
            proba = pipeline.predict_proba([combined_text])[0]
            pred_idx = list(classes).index(pred)
            conf = proba[pred_idx] * 100
            
            header_display = header.strip() if header else "(No Header)"
            print(f"  + {header_display} -> PREDICTED: {pred.upper()} ({conf:.1f}%)")

if __name__ == "__main__":
    main()
