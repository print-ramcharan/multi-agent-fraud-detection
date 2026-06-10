"""
Fraud Detection Model Training Pipeline

Trains a Random Forest classifier on synthetic transaction data.
Evaluates with accuracy, precision, recall, F1, and AUC-ROC.
Saves the trained model and feature names for inference.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

# Reproducibility
SEED = 42
np.random.seed(SEED)

# Paths (relative to this script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "training_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
FEATURES_PATH = os.path.join(BASE_DIR, "feature_names.json")


def load_data(path: str) -> pd.DataFrame:
    """Load the training CSV."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Training data not found at {path}. "
            "Run `python ml/synthetic_data.py` first."
        )
    df = pd.read_csv(path)
    print(f"Loaded {len(df):,} transactions from {path}")
    return df


def prepare_features(df: pd.DataFrame):
    """Split into feature matrix X and label vector y."""
    label_col = "is_fraud"
    feature_cols = [c for c in df.columns if c != label_col]

    X = df[feature_cols].values
    y = df[label_col].values

    return X, y, feature_cols


def train(X_train, y_train):
    """Train a Random Forest with balanced class weights."""
    clf = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=SEED,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    return clf


def evaluate(clf, X_test, y_test, feature_names: list[str]):
    """Print comprehensive evaluation metrics."""
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)

    print("\n" + "=" * 60)
    print("MODEL EVALUATION RESULTS")
    print("=" * 60)
    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {prec:.4f}")
    print(f"  Recall    : {rec:.4f}")
    print(f"  F1 Score  : {f1:.4f}")
    print(f"  AUC-ROC   : {auc:.4f}")

    print("\n--- Classification Report ---")
    print(classification_report(y_test, y_pred, target_names=["Legitimate", "Fraud"]))

    print("--- Confusion Matrix ---")
    cm = confusion_matrix(y_test, y_pred)
    print(f"  TN={cm[0][0]:>5,}   FP={cm[0][1]:>5,}")
    print(f"  FN={cm[1][0]:>5,}   TP={cm[1][1]:>5,}")

    # Feature importance ranking
    importances = clf.feature_importances_
    indices = np.argsort(importances)[::-1]
    print("\n--- Feature Importances (Top 10) ---")
    for rank, idx in enumerate(indices[:10], 1):
        print(f"  {rank:>2}. {feature_names[idx]:<28s} {importances[idx]:.4f}")
    print()

    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "auc_roc": auc}


def save_model(clf, feature_names: list[str]):
    """Persist the model and feature names to disk."""
    joblib.dump(clf, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    with open(FEATURES_PATH, "w") as f:
        json.dump(feature_names, f, indent=2)
    print(f"Feature names saved to {FEATURES_PATH}")


if __name__ == "__main__":
    # 1. Load data
    df = load_data(DATA_PATH)

    # 2. Prepare features
    X, y, feature_names = prepare_features(df)
    print(f"Features ({len(feature_names)}): {feature_names}")
    print(f"Label distribution: {dict(zip(*np.unique(y, return_counts=True)))}")

    # 3. Stratified train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=SEED
    )
    print(f"\nTrain set: {len(X_train):,} samples")
    print(f"Test  set: {len(X_test):,} samples")

    # 4. Train
    print("\nTraining Random Forest …")
    clf = train(X_train, y_train)
    print("Training complete.")

    # 5. Evaluate
    metrics = evaluate(clf, X_test, y_test, feature_names)

    # 6. Save
    save_model(clf, feature_names)
    print("\n✅ Pipeline finished successfully.")
