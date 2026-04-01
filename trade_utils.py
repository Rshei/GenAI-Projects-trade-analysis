"""
Utilities and helpers for the trade screening system.
"""

from __future__ import annotations

from typing import Dict, List
import pandas as pd


def format_currency(value: float) -> str:
    """Format value as currency."""
    return f"${value:,.2f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format value as percentage."""
    return f"{value:.{decimals}f}%"


def calculate_risk_reward_ratio(entry: float, stop_loss: float, take_profit: float) -> float:
    """Calculate risk/reward ratio.
    
    Risk/Reward = (Take Profit - Entry) / (Entry - Stop Loss)
    """
    risk = entry - stop_loss
    if risk <= 0:
        return 0.0
    reward = take_profit - entry
    return reward / risk


def calculate_position_size(account_size: float, risk_pct: float, entry: float, stop_loss: float) -> float:
    """Calculate position size based on account size and risk percentage.
    
    Position Size = (Account Size * Risk %) / (Entry - Stop Loss)
    """
    risk_amount = account_size * (risk_pct / 100.0)
    per_unit_risk = entry - stop_loss
    if per_unit_risk <= 0:
        return 0.0
    return risk_amount / per_unit_risk


def classify_setup_type(setup: str) -> str:
    """Classify setup into categories."""
    if "oversold" in setup.lower() or "rsi" in setup.lower():
        return "Mean Reversion"
    elif "breakout" in setup.lower() or "breakout" in setup.lower():
        return "Breakout"
    elif "swing" in setup.lower():
        return "Swing Trade"
    elif "macd" in setup.lower():
        return "Momentum"
    elif "bounce" in setup.lower():
        return "Bounce"
    return "Mixed"


def score_volatility_impact(atr: float, close: float) -> float:
    """Score volatility as percentage of price. Higher = more risk."""
    if close <= 0:
        return 0.5
    volatility_pct = (atr / close) * 100
    # Normalize to 0-1 scale
    return min(1.0, volatility_pct / 5.0)  # Treat 5% ATR as high volatility


def identify_trend_strength(ma50: float, ma200: float, close: float) -> str:
    """Identify trend strength based on moving averages."""
    if ma50 > ma200:
        if close > ma50:
            return "strong_uptrend"
        elif close > ma200:
            return "weak_uptrend"
        else:
            return "reversal_down"
    else:
        if close < ma50:
            return "strong_downtrend"
        elif close < ma200:
            return "weak_downtrend"
        else:
            return "reversal_up"
    return "neutral"


def filter_ideas_by_risk_reward(ideas: List[Dict], min_ratio: float = 1.5) -> List[Dict]:
    """Filter trade ideas by minimum risk/reward ratio."""
    filtered = []
    for idea in ideas:
        ratio = calculate_risk_reward_ratio(
            idea.get("entry", 0),
            idea.get("stop_loss", 0),
            idea.get("take_profit", 0)
        )
        if ratio >= min_ratio:
            idea["risk_reward_ratio"] = round(ratio, 2)
            filtered.append(idea)
    return filtered


def filter_ideas_by_volatility(ideas: List[Dict], max_atr_pct: float = 5.0) -> List[Dict]:
    """Filter trade ideas by maximum volatility."""
    filtered = []
    for idea in ideas:
        atr = idea.get("atr_stop_loss", idea.get("stop_loss", 0))
        close = idea.get("entry", 0)
        if atr and close:
            atr_pct = abs(close - atr) / close * 100
            if atr_pct <= max_atr_pct:
                filtered.append(idea)
    return filtered


def create_trade_plan(idea: Dict, account_size: float, risk_pct: float = 2.0) -> Dict:
    """Create detailed trade plan from an idea."""
    position_size = calculate_position_size(account_size, risk_pct, idea.get("entry", 0), idea.get("stop_loss", 0))
    risk_reward = calculate_risk_reward_ratio(idea.get("entry", 0), idea.get("stop_loss", 0), idea.get("take_profit", 0))
    
    return {
        "symbol": idea.get("symbol"),
        "setup": idea.get("setup"),
        "entry": format_currency(idea.get("entry", 0)),
        "stop_loss": format_currency(idea.get("stop_loss", 0)),
        "take_profit": format_currency(idea.get("take_profit", 0)),
        "position_size": round(position_size, 2),
        "risk_per_trade": format_currency(account_size * risk_pct / 100),
        "risk_reward_ratio": round(risk_reward, 2),
        "score": format_percentage(idea.get("composite_score", 0.5) * 100),
        "rationale": idea.get("rationale", ""),
    }


def export_trades_to_csv(ideas: List[Dict], filepath: str) -> None:
    """Export trade ideas to CSV with calculated fields."""
    rows = []
    for idea in ideas:
        row = {
            "Symbol": idea.get("symbol"),
            "Setup": classify_setup_type(idea.get("setup", "")),
            "Entry": idea.get("entry"),
            "Stop": idea.get("stop_loss"),
            "Target": idea.get("take_profit"),
            "R:R": calculate_risk_reward_ratio(idea.get("entry", 0), idea.get("stop_loss", 0), idea.get("take_profit", 0)),
            "Score": idea.get("composite_score", 0.5),
            "Rationale": idea.get("rationale", ""),
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(filepath, index=False)
