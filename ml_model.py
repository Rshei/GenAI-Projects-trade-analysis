"""
ML Model training for trade idea scoring.
Trains a RandomForest model on historical trade outcomes to predict success probability.
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    import joblib
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


MODEL_PATH = Path("models/ml_predictor.pkl")
SCALER_PATH = Path("models/scaler.pkl")


def prepare_training_data(analytics_path: str = "results/analytics/current_evaluations.csv") -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """
    Prepare training data from historical evaluations.
    Features: [rsi14, volume_score, market_cap_billions, is_bullish_macd]
    Target: 1 if trade hit target, 0 otherwise
    """
    if not HAS_SKLEARN:
        return None
    
    try:
        df = pd.read_csv(analytics_path)
        if df.empty or "return_pct" not in df.columns:
            return None
        
        # Create synthetic features from available data
        features = []
        targets = []
        
        for _, row in df.iterrows():
            ret_pct = float(row.get("return_pct", 0))
            target = 1 if ret_pct > 5.0 else 0  # Hit = 5%+ return
            
            # Build feature vector (note: some fields may not exist)
            feature_vec = [
                float(row.get("rsi14", 50)) if "rsi14" in row else 50,
                float(row.get("volume_score", 0.5)) if "volume_score" in row else 0.5,
                50.0,  # Default market cap in billions
                1.0 if str(row.get("setup", "")).lower() == "oversold_rsi" else 0.5,
            ]
            features.append(feature_vec)
            targets.append(target)
        
        if not features:
            return None
        
        X = np.array(features)
        y = np.array(targets)
        return X, y
    except Exception as e:
        print(f"Error preparing training data: {e}")
        return None


def train_model() -> Optional[RandomForestRegressor]:
    """Train a RandomForest model on historical data."""
    if not HAS_SKLEARN:
        print("sklearn not installed; skipping ML model training")
        return None
    
    data = prepare_training_data()
    if data is None:
        print("Insufficient historical data to train model")
        return None
    
    X, y = data
    
    try:
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train model
        model = RandomForestRegressor(
            n_estimators=50,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        model.fit(X_train, y_train)
        
        # Evaluate
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)
        print(f"Model trained: Train R² = {train_score:.3f}, Test R² = {test_score:.3f}")
        
        return model
    except Exception as e:
        print(f"Error training model: {e}")
        return None


def save_model(model: RandomForestRegressor) -> bool:
    """Save trained model to disk."""
    if not HAS_SKLEARN:
        return False
    
    try:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        print(f"Model saved to {MODEL_PATH}")
        return True
    except Exception as e:
        print(f"Error saving model: {e}")
        return False


def load_model() -> Optional[RandomForestRegressor]:
    """Load trained model from disk."""
    if not HAS_SKLEARN or not MODEL_PATH.exists():
        return None
    
    try:
        model = joblib.load(MODEL_PATH)
        return model
    except Exception:
        return None


def score_ideas_with_model(ideas: List[Dict], model: Optional[RandomForestRegressor] = None) -> List[Dict]:
    """Score trade ideas using trained ML model."""
    if not HAS_SKLEARN or model is None:
        # Return as-is if no model
        return ideas
    
    for idea in ideas:
        try:
            features = [
                float(idea.get("rsi14", 50)),
                float(idea.get("volume_score", 0.5)),
                float(idea.get("market_cap", 50e9)) / 1e9,
                0.8 if idea.get("macd_signal") == "bullish" else 0.3,
            ]
            
            # Predict success probability
            pred = model.predict([features])[0]
            ml_score = max(0.0, min(1.0, pred))
            idea["ml_score"] = round(ml_score, 3)
            
            # Blend with composite score
            composite = float(idea.get("composite_score", 0.5))
            idea["final_score"] = round(composite * 0.6 + ml_score * 0.4, 3)
        except Exception:
            idea["ml_score"] = 0.5
            idea["final_score"] = idea.get("composite_score", 0.5)
    
    return ideas


if __name__ == "__main__":
    # Train and save model
    model = train_model()
    if model:
        save_model(model)
