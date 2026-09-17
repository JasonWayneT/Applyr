#!/usr/bin/env python3
"""Train a candidate Stage 0 extractor from base and human-reviewed labels."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

# Implements FR-327 / AC-425: unreviewed fallback labels never enter retraining.
_ROOT = Path(__file__).resolve().parent.parent
_BASE = _ROOT / "data" / "training_data_clean.csv"
_REVIEWED = _ROOT / "data" / "training_data_approved.csv"
_LIVE = _ROOT / "data" / "stage0_classifier.pkl"
_CANDIDATE = _ROOT / "data" / "stage0_classifier.candidate.pkl"
_REPORT = _ROOT / "data" / "stage0_classifier.candidate.report.json"
LABELS = {"required", "preferred", "responsibilities", "culture"}


def load_rows(path: Path, *, reviewed: bool = False) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if not row.get("text", "").strip() or row.get("label") not in LABELS:
            raise ValueError(f"Invalid training row in {path.name}")
        if reviewed:
            if not all(row.get(key, "").strip() for key in ("company", "source_file", "reviewed_by", "reviewed_at")):
                raise ValueError("Approved feedback requires company, source_file, reviewed_by, and reviewed_at")
            if row["reviewed_by"].strip().casefold() in {"model", "llm", "harness", "fallback_api", "feedbackloop"}:
                raise ValueError("Approved feedback requires a human reviewer")
            try:
                stamp = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Approved feedback has invalid reviewed_at") from exc
            if stamp.tzinfo is None:
                raise ValueError("Approved feedback reviewed_at must have a timezone")
    return rows


def _group(row: dict[str, str]) -> str:
    return (row.get("company") or row.get("source_file") or "").strip().casefold()


def split_by_company(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    groups = [_group(row) for row in rows]
    if len(set(groups)) < 2 or any(not group for group in groups):
        raise ValueError("At least two identifiable company groups are required")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(splitter.split(rows, groups=groups))
    return [rows[i] for i in train_idx], [rows[i] for i in test_idx]


def train_candidate(base_path: Path = _BASE, reviewed_path: Path = _REVIEWED,
                    candidate_path: Path = _CANDIDATE, report_path: Path = _REPORT) -> dict:
    base = load_rows(base_path)
    if not base:
        raise ValueError("Base training data is missing")
    train, holdout = split_by_company(base)
    held_out_groups = {_group(row) for row in holdout}
    held_out_texts = {row["text"].strip().casefold() for row in holdout}
    reviewed = load_rows(reviewed_path, reviewed=True)
    train = [row for row in train if row["text"].strip().casefold() not in held_out_texts]
    train.extend(row for row in reviewed if _group(row) not in held_out_groups and row["text"].strip().casefold() not in held_out_texts)
    seen: set[tuple[str, str]] = set()
    unique_train = []
    for row in train:
        key = (row["text"].strip().casefold(), row["label"])
        if key not in seen:
            unique_train.append(row)
            seen.add(key)
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 3), max_df=0.9, min_df=2)),
        ("clf", LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)),
    ])
    pipeline.fit([row["text"] for row in unique_train], [row["label"] for row in unique_train])
    expected = [row["label"] for row in holdout]
    predicted = pipeline.predict([row["text"] for row in holdout])
    report = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "base_rows": len(base),
        "reviewed_rows": len(reviewed),
        "train_rows": len(unique_train),
        "holdout_rows": len(holdout),
        "holdout_companies": len(held_out_groups),
        "train_labels": dict(Counter(row["label"] for row in unique_train)),
        "holdout_metrics": classification_report(expected, predicted, output_dict=True, zero_division=0),
        "warning": "Candidate only. Promotion requires independent Stage 0 replay and false-skip review.",
    }
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, candidate_path)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def validate_replay_report(path: Path, candidate_path: Path) -> None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Replay report is missing or invalid JSON") from exc
    candidate_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    if not isinstance(report, dict) or report.get("candidate_sha256") != candidate_hash:
        raise ValueError("Replay report does not match the candidate model")
    if type(report.get("jd_count")) is not int or report["jd_count"] < 30:
        raise ValueError("Replay report requires at least 30 JDs")
    if type(report.get("false_skips")) is not int or report["false_skips"] != 0:
        raise ValueError("Replay report must have zero false skips")
    if type(report.get("silent_losses")) is not int or report["silent_losses"] != 0:
        raise ValueError("Replay report must have zero silent losses")
    reviewer = report.get("reviewed_by")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Replay report requires a human reviewer")
    if reviewer.strip().casefold() in {"model", "llm", "harness", "fallback_api", "feedbackloop"}:
        raise ValueError("Replay report requires a human reviewer")
    try:
        reviewed_at = datetime.fromisoformat(report["reviewed_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError) as exc:
        raise ValueError("Replay report requires a valid review timestamp") from exc
    if reviewed_at.tzinfo is None:
        raise ValueError("Replay review timestamp must have a timezone")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--promote", action="store_true", help="Promote candidate after independent replay approval")
    parser.add_argument("--replay-report", type=Path, help="Adjudicated replay report tied to the candidate hash")
    args = parser.parse_args()
    if args.promote:
        if args.replay_report is None or not _CANDIDATE.exists() or not _REPORT.exists():
            parser.error("Promotion requires --replay-report and an existing candidate/report")
        try:
            validate_replay_report(args.replay_report, _CANDIDATE)
        except ValueError as exc:
            parser.error(str(exc))
        if _LIVE.exists():
            shutil.copy2(_LIVE, _LIVE.with_name("stage0_classifier.previous.pkl"))
        shutil.copy2(_CANDIDATE, _LIVE)
        print(f"Promoted {_CANDIDATE.name} to {_LIVE.name}")
        return
    print(json.dumps(train_candidate(), indent=2))


if __name__ == "__main__":
    main()
