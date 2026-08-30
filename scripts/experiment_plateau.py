#!/usr/bin/env python3
import csv
import random
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

_REPO_ROOT = Path(__file__).parent.parent
_INPUT_CSV = _REPO_ROOT / "data" / "training_data_clean.csv"

def generate_synthetic_data(num_preferred, num_culture):
    techs = ["SQL", "Python", "React", "AWS", "Machine Learning", "Agile", "Scrum", "Jira", "Figma", "Data Analysis", "B2B SaaS", "APIs", "Microservices", "Docker", "Kubernetes"]
    culture_perks = ["health insurance", "dental and vision", "401k match", "unlimited PTO", "flexible working hours", "remote work options", "parental leave", "gym stipend", "learning and development budget", "work life balance"]
    culture_values = ["diversity and inclusion", "collaboration", "innovation", "customer obsession", "bias for action", "ownership", "transparency"]
    
    synthetic = []
    
    for _ in range(num_preferred):
        t = random.choice(techs)
        templates = [f"Bonus points for experience with {t}", f"Familiarity with {t} is a strong plus", f"Nice to have: knowledge of {t}", f"Ideally, you have shipped products using {t}", f"Previous experience with {t} preferred", f"A background in {t} would be beneficial", f"Experience working with {t} is advantageous"]
        synthetic.append({"text": random.choice(templates), "label": "preferred"})
        
    for _ in range(num_culture):
        p = random.choice(culture_perks)
        v = random.choice(culture_values)
        templates = [f"We offer comprehensive {p} for all employees.", f"Competitive benefits package including {p}.", f"Our culture is built on {v}.", f"We strongly believe in {v} and it drives our decisions.", f"Enjoy {p} as part of our commitment to {v}.", f"Join a team that values {v} above all else.", f"We prioritize {v} to ensure a healthy work environment."]
        synthetic.append({"text": random.choice(templates), "label": "culture"})
        
    return synthetic

def main():
    texts = []
    labels = []
    with open(_INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row["text"])
            labels.append(row["label"])
            
    print("Testing synthetic data plateaus...")
    increments = [(0,0), (1000, 500), (2000, 1000), (4000, 2000), (8000, 4000)]
    
    for pref, cult in increments:
        syn_texts = texts.copy()
        syn_labels = labels.copy()
        
        if pref > 0:
            synth_data = generate_synthetic_data(pref, cult)
            for row in synth_data:
                syn_texts.append(row["text"])
                syn_labels.append(row["label"])
                
        X_train, X_test, y_train, y_test = train_test_split(
            syn_texts, syn_labels, test_size=0.2, random_state=42, stratify=syn_labels
        )
        
        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(lowercase=True, ngram_range=(1, 3), max_df=0.9, min_df=2)),
            ('clf', LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000))
        ])
        
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        
        print(f"Added {pref+cult} synthetic rows -> Total: {len(syn_texts)} | Accuracy: {acc*100:.1f}%")

if __name__ == "__main__":
    main()
