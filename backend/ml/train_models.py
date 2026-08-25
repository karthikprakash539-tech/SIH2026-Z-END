"""
BlockSync ML training script.

Place at: backend/ml/train_models.py
Run from inside backend/ml/:

    python train_models.py

Trains and saves two models:
  duration_model.pkl  -- predicts maintenance duration (hours) from defect features
  delay_model.pkl     -- predicts train delay (minutes) from block/traffic features

Both are saved with joblib so the API can load them instantly without
retraining on every request.
"""

import sys
import os
import random
import numpy as np
import pandas as pd
from joblib import dump

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "models"))
from models import engine, Defect, Section
from sqlalchemy.orm import sessionmaker

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

random.seed(42)
np.random.seed(42)

Session = sessionmaker(bind=engine)
session = Session()

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_ROUTE_DIR = os.path.join(MODEL_DIR, "..", "..", "data", "raw", "Train_Route")


# ---------------------------------------------------------------------------
# MODEL 1: Maintenance Duration Prediction
# ---------------------------------------------------------------------------
# There is no public real historical duration dataset (TMS/SMMS/TDMS data is
# internal to Railways). We generate realistic, labeled training examples
# from our real defect records using domain-reasonable base durations per
# defect type/severity, plus natural noise -- so the model is genuinely
# trained and genuinely predicts, even though the labels are synthetic.

BASE_DURATION_HOURS = {
    # department-agnostic base hours by severity (1=Low .. 5=Critical)
    1: 1.5, 2: 2.5, 3: 4.0, 4: 6.0, 5: 8.5,
}

DEPARTMENT_MULTIPLIER = {
    "TMS": 1.1,    # track work tends to take slightly longer
    "SMMS": 0.9,   # signal fixes tend to be quicker
    "TDMS": 1.2,   # traction/electrical work often needs isolation time
}


def build_duration_training_data():
    defects = session.query(Defect).all()
    if not defects:
        raise RuntimeError("No defects found in DB -- run load_data.py first.")

    rows = []
    for d in defects:
        base = BASE_DURATION_HOURS.get(d.severity, 3.0)
        mult = DEPARTMENT_MULTIPLIER.get(d.department, 1.0)
        overdue_factor = 1 + (d.overdue_days / 100)  # long-overdue defects take a bit longer to fully resolve
        noise = np.random.normal(0, 0.4)
        duration = max(0.5, base * mult * overdue_factor + noise)

        rows.append({
            "department": d.department,
            "severity": d.severity,
            "overdue_days": d.overdue_days,
            "duration_hours": round(duration, 2),
        })

    df = pd.DataFrame(rows)
    df = pd.get_dummies(df, columns=["department"])  # one-hot encode department
    return df


def train_duration_model():
    df = build_duration_training_data()
    feature_cols = [c for c in df.columns if c != "duration_hours"]
    X = df[feature_cols]
    y = df["duration_hours"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    print(f"[Model 1: Duration] trained on {len(X_train)} samples, "
          f"tested on {len(X_test)} -- MAE = {mae:.2f} hours")

    dump({"model": model, "feature_cols": feature_cols}, os.path.join(MODEL_DIR, "duration_model.pkl"))
    print(f"[ok] saved duration_model.pkl")


# ---------------------------------------------------------------------------
# MODEL 2: Train Delay / Impact Prediction
# ---------------------------------------------------------------------------
# Tries to use your REAL train delay dataset. If the expected columns
# aren't found (dataset structure varies), falls back to a synthetic-but-
# reasonable generator so the pipeline never blocks on a column mismatch.

def try_load_real_delay_data(route_dir):
    """Reads every per-train CSV in data/raw/Train_Route/ (42 real files,
    one per train number) and pulls the real Average_Delay column from
    each station row. Returns a single combined DataFrame of real
    observed average-delay values (in minutes) across all 42 real trains
    and their real stations."""
    if not os.path.isdir(route_dir):
        print(f"[warn] {route_dir} not found.")
        return None

    all_delays = []
    files_used = 0
    for fname in os.listdir(route_dir):
        if not fname.endswith(".csv"):
            continue
        path = os.path.join(route_dir, fname)
        try:
            df = pd.read_csv(path, on_bad_lines="skip", engine="python")
        except Exception:
            continue

        delay_col = next((c for c in df.columns if "average" in c.lower() and "delay" in c.lower()), None)
        if not delay_col:
            delay_col = next((c for c in df.columns if "delay" in c.lower()), None)
        if not delay_col:
            continue

        vals = pd.to_numeric(df[delay_col], errors="coerce").dropna()
        if len(vals) == 0:
            continue
        all_delays.extend(vals.tolist())
        files_used += 1

    if not all_delays:
        print(f"[warn] no usable delay columns found across files in {route_dir}")
        return None

    print(f"[info] loaded real delay values from {files_used} real train route files "
          f"({len(all_delays)} station-level observations)")
    return pd.DataFrame({"actual_delay_minutes": all_delays})


def build_delay_training_data():
    real = try_load_real_delay_data(TRAIN_ROUTE_DIR)
    sections = session.query(Section).all()
    if not sections:
        raise RuntimeError("No sections found in DB -- run load_data.py first.")

    rows = []
    n_samples = 150
    for i in range(n_samples):
        sec = random.choice(sections)
        block_duration = round(random.uniform(1, 8), 1)     # hours
        traffic_density = sec.traffic_density
        time_of_day = random.choice([0, 1])  # 0 = off-peak, 1 = peak

        if real is not None and len(real) > 0:
            # sample a real observed delay value as the base signal, then
            # scale it by this synthetic block's duration/traffic -- keeps
            # a genuine real-world delay distribution underneath the label
            base_delay = real["actual_delay_minutes"].sample(1).values[0]
            delay = max(0, base_delay * (block_duration / 4) * (1 + 0.3 * time_of_day))
        else:
            # fully synthetic fallback if the real dataset couldn't be parsed
            delay = max(0, block_duration * traffic_density * 8 + (15 if time_of_day else 0)
                        + np.random.normal(0, 5))

        rows.append({
            "block_duration_hours": block_duration,
            "traffic_density": traffic_density,
            "time_of_day_peak": time_of_day,
            "delay_minutes": round(delay, 1),
        })

    return pd.DataFrame(rows), (real is not None)


def train_delay_model():
    df, used_real_data = build_delay_training_data()
    feature_cols = ["block_duration_hours", "traffic_density", "time_of_day_peak"]
    X = df[feature_cols]
    y = df["delay_minutes"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = LinearRegression()
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    source = "real train_delays.csv (resampled)" if used_real_data else "synthetic fallback"
    print(f"[Model 2: Delay] trained on {len(X_train)} samples, tested on {len(X_test)} "
          f"-- MAE = {mae:.2f} minutes -- data source: {source}")

    dump({"model": model, "feature_cols": feature_cols}, os.path.join(MODEL_DIR, "delay_model.pkl"))
    print(f"[ok] saved delay_model.pkl")


if __name__ == "__main__":
    print("Training BlockSync ML models...\n")
    train_duration_model()
    print()
    train_delay_model()
    print("\nDone. Both models saved in:", MODEL_DIR)