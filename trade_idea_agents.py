from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from langchain_core.tools import tool
except Exception:
    class _FallbackTool:
        def __init__(self, fn):
            self._fn = fn
            self.__name__ = getattr(fn, "__name__", "tool")
            self.__doc__ = getattr(fn, "__doc__", "")

        def __call__(self, *args, **kwargs):
            return self._fn(*args, **kwargs)

        def invoke(self, payload: Optional[Dict] = None):
            payload = payload or {}
            return self._fn(**payload)

    def tool(fn):
        return _FallbackTool(fn)


class GuardError(RuntimeError):
    """Raised when tool guard constraints are violated."""


class ToolExecutionGuard:
    def __init__(self, max_tool_calls: int = 500) -> None:
        self.max_tool_calls = max_tool_calls
        self.reset()

    def reset(self) -> None:
        self.call_count = 0
        self.fingerprints: set[str] = set()

    def register(self, tool_name: str, payload: Dict) -> None:
        self.call_count += 1
        if self.call_count > self.max_tool_calls:
            raise GuardError(f"Exceeded max tool calls: {self.max_tool_calls}")

        payload_str = json.dumps(payload, sort_keys=True, default=str)
        fingerprint = sha256(f"{tool_name}:{payload_str}".encode("utf-8")).hexdigest()
        if fingerprint in self.fingerprints:
            raise GuardError(f"Duplicate tool payload detected for {tool_name}")
        self.fingerprints.add(fingerprint)


GUARD = ToolExecutionGuard(500)


@dataclass
class StockSnapshot:
    symbol: str
    market_cap: float
    close: float
    prev_close: float
    ma50: float
    prev_ma50: float
    rsi14: float


@dataclass
class TradeIdea:
    symbol: str
    setup: str
    entry: float
    stop_loss: float
    take_profit: float
    market_cap: float
    rsi14: float
    ma50: float
    rationale: str
    atr_stop_loss: Optional[float] = None
    macd_signal: Optional[str] = None
    volume_score: Optional[float] = None
    ml_score: Optional[float] = None
    news_sentiment: Optional[float] = None
    buzz_score: Optional[float] = None


def compute_rsi(close_series: pd.Series, period: int = 14) -> pd.Series:
    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return atr.fillna(0)


def compute_macd(close_series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """Calculate MACD and signal line. Returns (macd, signal_line)."""
    ema_fast = close_series.ewm(span=fast, adjust=False).mean()
    ema_slow = close_series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def compute_bollinger_bands(close_series: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple:
    """Calculate Bollinger Bands. Returns (upper, middle, lower)."""
    middle = close_series.rolling(window=period).mean()
    std = close_series.rolling(window=period).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return upper, middle, lower


FALLBACK_SP500 = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "GOOG",
    "META",
    "BRK-B",
    "LLY",
    "AVGO",
    "TSLA",
    "JPM",
    "V",
    "UNH",
    "XOM",
    "MA",
    "COST",
    "JNJ",
    "PG",
    "HD",
    "ABBV",
    "MRK",
    "KO",
    "PEP",
    "BAC",
    "ADBE",
    "CRM",
    "WMT",
    "CSCO",
    "MCD",
    "TMO",
    "ACN",
    "LIN",
    "ABT",
    "DHR",
    "VZ",
    "CMCSA",
    "NFLX",
    "NKE",
    "AMD",
    "INTC",
    "DIS",
    "TXN",
    "QCOM",
    "PM",
    "HON",
    "ORCL",
    "UNP",
    "LOW",
    "IBM",
    "AMAT",
    "CAT",
    "GE",
    "GS",
    "SBUX",
    "INTU",
    "ISRG",
    "BKNG",
    "SPGI",
    "BLK",
    "GILD",
    "SYK",
    "ADP",
    "MMC",
    "PLD",
    "MDT",
    "AXP",
    "DE",
    "MO",
    "VRTX",
    "LMT",
    "TJX",
    "PGR",
    "CB",
    "SO",
    "CI",
    "NOW",
    "ETN",
    "COP",
    "C",
    "ADSK",
    "AMGN",
    "TMUS",
    "UPS",
    "SCHW",
    "ELV",
    "NEE",
    "CSX",
    "FISV",
    "KLAC",
    "MU",
    "T",
    "PYPL",
    "REGN",
    "SHW",
    "ZTS",
    "ICE",
    "AON",
    "SNPS",
    "EQIX",
    "MCO",
    "PANW",
]


@tool
def get_sp500_universe(limit: int = 120) -> List[str]:
    """Get S&P 500 ticker symbols from Wikipedia, with fallback list."""
    GUARD.register("get_sp500_universe", {"limit": limit})

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        )
    }

    symbols: List[str]
    try:
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        tables = pd.read_html(response.text)
        sp500_table = tables[0]
        symbols = (
            sp500_table["Symbol"].astype(str).str.strip().str.replace(".", "-", regex=False).tolist()
        )
    except Exception:
        symbols = FALLBACK_SP500.copy()

    return symbols[:limit]


@tool
def get_ticker_snapshot(symbol: str, lookback_days: int = 260) -> Optional[Dict]:
    """Fetch market cap and technical snapshot for one symbol."""
    GUARD.register(
        "get_ticker_snapshot",
        {"symbol": symbol, "lookback_days": lookback_days},
    )

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        market_cap = float(info.get("marketCap") or 0)
        if market_cap < 1_000_000_000:
            return None

        history = ticker.history(period=f"{lookback_days}d", auto_adjust=False)
        if history is None or history.empty or "Close" not in history.columns:
            return None

        close = history["Close"].dropna()
        if len(close) < 60:
            return None

        # Core indicators
        ma50 = close.rolling(window=50).mean()
        ma200 = close.rolling(window=200).mean()
        rsi14 = compute_rsi(close, period=14)
        
        # Additional technical indicators
        if "High" in history.columns and "Low" in history.columns:
            atr = compute_atr(history["High"], history["Low"], close, period=14)
            atr_val = float(atr.iloc[-1])
        else:
            atr_val = None
        
        macd_line, macd_signal = compute_macd(close)
        macd_signal_val = "bullish" if macd_line.iloc[-1] > macd_signal.iloc[-1] else "bearish"
        
        upper_bb, middle_bb, lower_bb = compute_bollinger_bands(close, period=20)
        
        # Volume score
        volume_score = 0.5
        if "Volume" in history.columns:
            volume = history["Volume"].dropna()
            if len(volume) > 20:
                avg_vol = volume.iloc[-20:].mean()
                current_vol = float(volume.iloc[-1])
                volume_score = min(1.0, current_vol / avg_vol * 0.5)
        
        if pd.isna(ma50.iloc[-1]) or pd.isna(ma50.iloc[-2]):
            return None

        snapshot = StockSnapshot(
            symbol=symbol,
            market_cap=market_cap,
            close=float(close.iloc[-1]),
            prev_close=float(close.iloc[-2]),
            ma50=float(ma50.iloc[-1]),
            prev_ma50=float(ma50.iloc[-2]),
            rsi14=float(rsi14.iloc[-1]),
        )
        snap_dict = asdict(snapshot)
        
        # Add extended metrics
        snap_dict["ma200"] = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else None
        snap_dict["atr"] = atr_val
        snap_dict["macd_signal"] = macd_signal_val
        snap_dict["bb_upper"] = float(upper_bb.iloc[-1]) if not pd.isna(upper_bb.iloc[-1]) else None
        snap_dict["bb_lower"] = float(lower_bb.iloc[-1]) if not pd.isna(lower_bb.iloc[-1]) else None
        snap_dict["volume_score"] = volume_score
        
        return snap_dict
    except Exception:
        return None


@tool
def screen_for_setups(snapshots: List[Dict], rsi_threshold: float = 35.0) -> List[Dict]:
    """Screen snapshots for multiple technical setups (RSI, MA50, swing, MACD, BB)."""
    GUARD.register(
        "screen_for_setups",
        {
            "snapshots": snapshots,
            "rsi_threshold": rsi_threshold,
        },
    )

    candidates: List[Dict] = []
    for snap in snapshots:
        if not snap:
            continue

        # Setup 1: RSI Oversold
        if float(snap["rsi14"]) < rsi_threshold:
            row = dict(snap)
            row["setup"] = "oversold_rsi"
            candidates.append(row)

        # Setup 2: MA50 Breakout
        if float(snap["close"]) > float(snap["ma50"]) and float(snap["prev_close"]) <= float(snap["prev_ma50"]):
            row = dict(snap)
            row["setup"] = "ma50_breakout"
            candidates.append(row)
        
        # Setup 3: Swing Reversal (pulled back near MA50 after uptrend)
        if snap.get("ma200") and float(snap["close"]) < float(snap["ma50"]) < float(snap.get("ma200", snap["ma50"])):
            if float(snap["rsi14"]) < 60:
                row = dict(snap)
                row["setup"] = "swing_reversal"
                candidates.append(row)
        
        # Setup 4: MACD Bullish Crossover
        if snap.get("macd_signal") == "bullish" and float(snap["rsi14"]) > 40:
            row = dict(snap)
            row["setup"] = "macd_bullish"
            candidates.append(row)
        
        # Setup 5: Bollinger Band Bounce (price near lower band)
        if snap.get("bb_lower") and snap.get("bb_upper"):
            bb_range = float(snap["bb_upper"]) - float(snap["bb_lower"])
            if bb_range > 0:
                price_ratio = (float(snap["close"]) - float(snap["bb_lower"])) / bb_range
                if price_ratio < 0.15:  # Close to lower band
                    row = dict(snap)
                    row["setup"] = "bb_bounce"
                    candidates.append(row)

    return candidates


@tool
def generate_trade_ideas(candidates: List[Dict]) -> List[Dict]:
    """Convert screened candidates into structured trade ideas with ATR-based stops."""
    GUARD.register("generate_trade_ideas", {"candidates": candidates})

    ideas: List[Dict] = []
    for c in candidates:
        entry = round(float(c["close"]), 2)
        
        # ATR-based stop loss if available
        if c.get("atr"):
            stop_loss = round(entry - float(c["atr"]) * 2, 2)
        else:
            stop_loss = round(entry * 0.95, 2)
        
        take_profit = round(entry * 1.15, 2)

        # Setup-specific rationale
        if c["setup"] == "oversold_rsi":
            rationale = (
                f"RSI14 at {float(c['rsi14']):.1f} signals oversold; watch for mean reversion bounce."
            )
        elif c["setup"] == "ma50_breakout":
            rationale = "Price broke above MA50; possible trend continuation breakout."
        elif c["setup"] == "swing_reversal":
            rationale = "Price pulled back near MA50 after strong uptrend; swing entry near support."
        elif c["setup"] == "macd_bullish":
            rationale = "MACD bullish crossover with RSI above 40; momentum confirmation."
        elif c["setup"] == "bb_bounce":
            rationale = "Price near lower Bollinger Band; mean reversion opportunity."
        else:
            rationale = f"Trading setup: {c['setup']}"

        idea = TradeIdea(
            symbol=str(c["symbol"]),
            setup=str(c["setup"]),
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            market_cap=float(c["market_cap"]),
            rsi14=float(c["rsi14"]),
            ma50=round(float(c["ma50"]), 2),
            rationale=rationale,
            atr_stop_loss=round(entry - float(c.get("atr", 0)) * 2, 2) if c.get("atr") else None,
            macd_signal=c.get("macd_signal"),
            volume_score=c.get("volume_score"),
        )
        ideas.append(asdict(idea))

    return ideas


@tool
def rank_trade_ideas(ideas: List[Dict], top_n: int = 10) -> List[Dict]:
    """Rank ideas by setup-specific criteria with ML scoring."""
    GUARD.register("rank_trade_ideas", {"ideas": ideas, "top_n": top_n})

    # Score each idea
    for idea in ideas:
        score = 0.5  # Base score
        
        # Setup-specific scores
        setup = idea.get("setup", "")
        if setup == "oversold_rsi":
            rsi = float(idea.get("rsi14", 50))
            score += (35 - rsi) / 35.0 * 0.2  # Deeper oversold = better
        elif setup == "ma50_breakout":
            score += 0.15
        elif setup == "swing_reversal":
            score += 0.18
        elif setup == "macd_bullish":
            score += 0.15
        elif setup == "bb_bounce":
            score += 0.12
        
        # Volume bonus
        vol_score = float(idea.get("volume_score", 0.5))
        score += vol_score * 0.15
        
        # Market cap adjustment (prefer larger caps for stability)
        market_cap = float(idea.get("market_cap", 1e9))
        if market_cap > 50e9:
            score += 0.05
        
        idea["composite_score"] = min(1.0, score)
    
    # Sort by composite score
    ranked = sorted(ideas, key=lambda x: float(x.get("composite_score", 0)), reverse=True)
    
    return ranked[:top_n]


def compute_ml_score(idea: Dict, trained_model=None) -> float:
    """
    Simple ML-based scoring. If sklearn is available and model is trained,
    use it; otherwise fall back to heuristic scoring.
    """
    if trained_model and HAS_SKLEARN:
        try:
            features = [
                float(idea.get("rsi14", 50)),
                float(idea.get("volume_score", 0.5)),
                float(idea.get("market_cap", 1e9)) / 1e9,
                0.8 if idea.get("macd_signal") == "bullish" else 0.2,
            ]
            prediction = trained_model.predict([features])[0]
            return max(0.0, min(1.0, prediction))
        except Exception:
            return 0.5
    
    # Fallback heuristic
    composite = idea.get("composite_score", 0.5)
    vol_bonus = float(idea.get("volume_score", 0.5)) * 0.2
    return min(1.0, composite + vol_bonus)


@tool
def get_news_sentiment(symbol: str) -> Dict:
    """Fetch news sentiment for a symbol. Returns buzz_score and sentiment."""
    GUARD.register("get_news_sentiment", {"symbol": symbol})
    
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
        
        if not news:
            return {"symbol": symbol, "news_count": 0, "buzz_score": 0.5, "sentiment": "neutral"}
        
        # Simple sentiment based on # of recent news items
        news_count = len(news)
        # Score: more recent news = higher buzz
        buzz_score = min(1.0, news_count / 20.0)  # Cap at 1.0 with 20+ news
        
        # Rough sentiment from headlines (very basic)
        positive_words = ["surge", "gain", "rally", "beat", "strong", "upbeat", "upgrade"]
        negative_words = ["fall", "decline", "drop", "miss", "weak", "downgrade", "tumble"]
        
        sentiment_score = 0.5
        for article in news[:10]:
            title = str(article.get("title", "")).lower()
            for word in positive_words:
                if word in title:
                    sentiment_score += 0.05
            for word in negative_words:
                if word in title:
                    sentiment_score -= 0.05
        
        sentiment_score = max(0.0, min(1.0, sentiment_score))
        sentiment = "bullish" if sentiment_score > 0.6 else ("bearish" if sentiment_score < 0.4 else "neutral")
        
        return {
            "symbol": symbol,
            "news_count": news_count,
            "buzz_score": round(buzz_score, 2),
            "sentiment": sentiment,
            "sentiment_score": round(sentiment_score, 2),
        }
    except Exception:
        return {"symbol": symbol, "news_count": 0, "buzz_score": 0.5, "sentiment": "neutral", "sentiment_score": 0.5}


def run_pipeline(universe_limit: int = 100, rsi_threshold: float = 35.0, top_n: int = 10, include_news: bool = True) -> Dict:
    GUARD.reset()
    symbols = get_sp500_universe.invoke({"limit": universe_limit})

    snapshots: List[Dict] = []
    for symbol in symbols:
        snap = get_ticker_snapshot.invoke({"symbol": symbol, "lookback_days": 260})
        if snap:
            snapshots.append(snap)

    candidates = screen_for_setups.invoke({"snapshots": snapshots, "rsi_threshold": rsi_threshold})
    ideas = generate_trade_ideas.invoke({"candidates": candidates})
    ranked = rank_trade_ideas.invoke({"ideas": ideas, "top_n": top_n * 2})  # Get 2x before filtering
    
    # Add news sentiment if requested
    if include_news:
        for idea in ranked:
            news_data = get_news_sentiment.invoke({"symbol": idea["symbol"]})
            idea["news_sentiment"] = news_data.get("sentiment_score", 0.5)
            idea["buzz_score"] = news_data.get("buzz_score", 0.5)
        
        # Re-rank with news boost
        for idea in ranked:
            idea["composite_score"] = float(idea.get("composite_score", 0.5)) * 0.7 + float(idea.get("news_sentiment", 0.5)) * 0.3
        ranked = sorted(ranked, key=lambda x: float(x.get("composite_score", 0)), reverse=True)

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "trade_ideas": ranked[:top_n],
        "symbols_screened": len(snapshots),
        "setups_found": len(ideas),
        "top_n": top_n,
    }


def save_results(result: Dict) -> Dict[str, str]:
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = results_dir / f"trade_ideas_{ts}.json"
    csv_path = results_dir / f"trade_ideas_{ts}.csv"
    latest_json = results_dir / "latest_trade_ideas.json"
    latest_csv = results_dir / "latest_trade_ideas.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    with latest_json.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    df = pd.DataFrame(result.get("trade_ideas", []))
    df.to_csv(csv_path, index=False)
    df.to_csv(latest_csv, index=False)

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "latest_json": str(latest_json),
        "latest_csv": str(latest_csv),
    }


if __name__ == "__main__":
    pipeline_result = run_pipeline()
    paths = save_results(pipeline_result)
    print(json.dumps({"result": pipeline_result, "saved": paths}, indent=2))
