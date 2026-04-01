"""
Trade Outcome Tracker: Track predicted vs. actual performance
Allows comparing trade ideas predictions to real outcomes over time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf


@dataclass
class TrackedTrade:
    """A trade idea tracked with metadata."""
    trade_id: str
    symbol: str
    setup: str
    predicted_at: str
    entry_price: float
    stop_loss: float
    take_profit: float
    initial_score: float
    
    # Outcome tracking (updated later)
    status: str = "open"  # open, closed_win, closed_loss, closed_target, closed_stop
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    actual_return_pct: Optional[float] = None
    dayshold: Optional[int] = None
    news_sentiment: Optional[float] = None
    buzz_score: Optional[float] = None
    ml_score: Optional[float] = None


def generate_trade_id(symbol: str, setup: str, timestamp: str) -> str:
    """Generate unique trade ID."""
    from hashlib import sha256
    data = f"{symbol}:{setup}:{timestamp}"
    hash_obj = sha256(data.encode()).hexdigest()
    return f"T_{hash_obj[:12]}"  # T_<first12_hex>
    

def create_tracked_trade(idea: Dict, predicted_at: Optional[str] = None) -> TrackedTrade:
    """Convert a trade idea into a tracked trade."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()
    
    trade_id = generate_trade_id(
        idea["symbol"],
        idea["setup"],
        predicted_at
    )
    
    return TrackedTrade(
        trade_id=trade_id,
        symbol=idea["symbol"],
        setup=idea["setup"],
        predicted_at=predicted_at,
        entry_price=float(idea["entry"]),
        stop_loss=float(idea["stop_loss"]),
        take_profit=float(idea["take_profit"]),
        initial_score=float(idea.get("composite_score", idea.get("final_score", 0.5))),
        news_sentiment=idea.get("news_sentiment"),
        buzz_score=idea.get("buzz_score"),
        ml_score=idea.get("ml_score"),
    )


class TradeOutcomeTracker:
    """Tracks predicted vs. actual trade outcomes."""
    
    def __init__(self, db_path: str = "results/trades_db.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.trades: Dict[str, TrackedTrade] = self._load_db()
    
    def _load_db(self) -> Dict[str, TrackedTrade]:
        """Load trade database from disk."""
        if not self.db_path.exists():
            return {}
        
        try:
            with self.db_path.open("r") as f:
                data = json.load(f)
            
            trades = {}
            for trade_id, trade_dict in data.items():
                trades[trade_id] = TrackedTrade(**trade_dict)
            return trades
        except Exception:
            return {}
    
    def _save_db(self) -> None:
        """Save trade database to disk."""
        try:
            data = {tid: asdict(t) for tid, t in self.trades.items()}
            with self.db_path.open("w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving trade DB: {e}")
    
    def add_trades(self, ideas: List[Dict], source_snapshot_id: str) -> List[str]:
        """Add new trade ideas to tracker."""
        added_ids = []
        for idea in ideas:
            tracked = create_tracked_trade(idea)
            self.trades[tracked.trade_id] = tracked
            added_ids.append(tracked.trade_id)
        
        self._save_db()
        return added_ids
    
    def update_trade_outcome(self, trade_id: str, exit_price: float, dayshold: int) -> Optional[Dict]:
        """Update a trade with its outcome."""
        if trade_id not in self.trades:
            return None
        
        trade = self.trades[trade_id]
        trade.exit_price = exit_price
        trade.exit_date = datetime.now(timezone.utc).isoformat()
        trade.dayshold = dayshold
        trade.actual_return_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        
        # Classify outcome
        if exit_price >= trade.take_profit:
            trade.status = "closed_target"
        elif exit_price <= trade.stop_loss:
            trade.status = "closed_stop"
        elif trade.actual_return_pct > 0:
            trade.status = "closed_win"
        else:
            trade.status = "closed_loss"
        
        self._save_db()
        return asdict(trade)
    
    def get_stats(self) -> Dict:
        """Get summary statistics."""
        closed = [t for t in self.trades.values() if "closed" in t.status]
        
        if not closed:
            return {
                "total_trades": len(self.trades),
                "closed_trades": 0,
                "open_trades": len(self.trades),
                "win_rate_pct": 0.0,
                "avg_return_pct": 0.0,
                "prediction_accuracy": None,
            }
        
        returns = [t.actual_return_pct for t in closed if t.actual_return_pct is not None]
        wins = [t for t in closed if t.status in ["closed_target", "closed_win"]]
        
        prediction_accuracy = None
        if all(t.initial_score is not None for t in closed):
            # Compare predicted scores to actual outcomes
            predicted = [t.initial_score for t in closed]
            actual = [1 if t.status in ["closed_target", "closed_win"] else 0 for t in closed]
            correlation = pd.Series(predicted).corr(pd.Series(actual))
            if not pd.isna(correlation):
                prediction_accuracy = round(correlation, 3)
        
        return {
            "total_trades": len(self.trades),
            "closed_trades": len(closed),
            "open_trades": len(self.trades) - len(closed),
            "win_rate_pct": round((len(wins) / len(closed) * 100), 2) if closed else 0.0,
            "avg_return_pct": round(sum(returns) / len(returns), 2) if returns else 0.0,
            "prediction_accuracy": prediction_accuracy,
        }
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get all trades as DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        
        rows = [asdict(t) for t in self.trades.values()]
        return pd.DataFrame(rows)
    
    def get_performance_by_setup(self) -> pd.DataFrame:
        """Get performance metrics grouped by setup."""
        df = self.get_trades_df()
        if df.empty:
            return pd.DataFrame()
        
        closed = df[df["status"].str.contains("closed")]
        if closed.empty:
            return pd.DataFrame()
        
        grouped = closed.groupby("setup").agg(
            count=("trade_id", "size"),
            avg_return=("actual_return_pct", "mean"),
            win_count=("status", lambda x: (x == "closed_target").sum() | (x == "closed_win").sum()),
        ).reset_index()
        
        grouped["win_rate_pct"] = (grouped["win_count"] / grouped["count"] * 100).round(2)
        grouped["avg_return"] = grouped["avg_return"].round(2)
        
        return grouped[["setup", "count", "avg_return", "win_rate_pct"]]


def main():
    """Example usage."""
    tracker = TradeOutcomeTracker()
    stats = tracker.get_stats()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
