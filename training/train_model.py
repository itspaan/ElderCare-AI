"""
Train a Random Forest Classifier on the elderly synthetic dataset.

Usage:
    python -m training.train_model

The script reads data/elderly_synthetic_data.csv, trains on the features
[Age, Systolic_BP, Blood_Sugar, Joint_Pain, Memory_Loss, Fatigue],
and saves the trained model + feature list to models/disease_model.pkl.
"""

import os
import pickle
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

# Feature columns used for training (must match the CSV)
FEATURES = [
    "Age",
    "Systolic_BP",
    "Blood_Sugar",
    "Joint_Pain",
    "Memory_Loss",
    "Fatigue",
]

TARGET = "Disease"

# Resolve paths relative to the project root (parent of this file's directory)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "elderly_synthetic_data.csv")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "disease_model.pkl")


def main():
    # ------------------------------------------------------------------
    # 1. Load dataset
    # ------------------------------------------------------------------
    if not os.path.exists(DATA_PATH):
        print(f"[ERROR] Dataset not found at {DATA_PATH}")
        print("  -> Run `python -m data.generate_dummy` first to create it.")
        return

    print(f"Loading dataset from {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)
    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
    print(f"  Disease distribution:\n{df[TARGET].value_counts().to_string()}\n")

    # ------------------------------------------------------------------
    # 2. Prepare features & target
    # ------------------------------------------------------------------
    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"  Train set: {len(X_train)} samples")
    print(f"  Test set:  {len(X_test)} samples\n")

    # ------------------------------------------------------------------
    # 3. Train model
    # ------------------------------------------------------------------
    print("Training Random Forest Classifier ...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # ------------------------------------------------------------------
    # 4. Evaluate
    # ------------------------------------------------------------------
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nModel Accuracy: {accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # ------------------------------------------------------------------
    # 5. Save model
    # ------------------------------------------------------------------
    os.makedirs(MODEL_DIR, exist_ok=True)

    model_data = {
        "model": model,
        "features": FEATURES,
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model_data, f)

    print(f"Model saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
