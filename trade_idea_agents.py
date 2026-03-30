from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.tools import tool
import pandas as pd
import requests
import yfinance as yf


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


def compute_rsi(close_series: pd.Series, period: int = 14) -> pd.Series:
    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


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

        ma50 = close.rolling(window=50).mean()
        rsi14 = compute_rsi(close, period=14)
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
        return asdict(snapshot)
    except Exception:
        return None


@tool
def screen_for_setups(snapshots: List[Dict], rsi_threshold: float = 35.0) -> List[Dict]:
    """Screen snapshots for RSI oversold and MA50 breakout setups."""
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

        if float(snap["rsi14"]) < rsi_threshold:
            row = dict(snap)
            row["setup"] = "oversold_rsi"
            candidates.append(row)

        if float(snap["close"]) > float(snap["ma50"]) and float(snap["prev_close"]) <= float(snap["prev_ma50"]):
            row = dict(snap)
            row["setup"] = "ma50_breakout"
            candidates.append(row)

    return candidates


@tool
def generate_trade_ideas(candidates: List[Dict]) -> List[Dict]:
    """Convert screened candidates into structured trade ideas."""
    GUARD.register("generate_trade_ideas", {"candidates": candidates})

    ideas: List[Dict] = []
    for c in candidates:
        entry = round(float(c["close"]), 2)
        stop_loss = round(entry * 0.95, 2)
        take_profit = round(entry * 1.15, 2)

        if c["setup"] == "oversold_rsi":
            rationale = (
                f"RSI14 is {float(c['rsi14']):.2f}, below oversold threshold; "
                "watch for mean reversion."
            )
        else:
            rationale = (
                "Price crossed above MA50 after being at or below it the prior day; "
                "possible trend continuation breakout."
            )

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
        )
        ideas.append(asdict(idea))

    return ideas


@tool
def rank_trade_ideas(ideas: List[Dict], top_n: int = 10) -> List[Dict]:
    """Rank ideas by setup-specific criteria and interleave setup groups."""
    GUARD.register("rank_trade_ideas", {"ideas": ideas, "top_n": top_n})

    oversold = [i for i in ideas if i.get("setup") == "oversold_rsi"]
    breakout = [i for i in ideas if i.get("setup") == "ma50_breakout"]

    oversold_sorted = sorted(oversold, key=lambda x: float(x.get("rsi14", 999)))
    breakout_sorted = sorted(breakout, key=lambda x: float(x.get("market_cap", 0)), reverse=True)

    ranked: List[Dict] = []
    i = 0
    while len(ranked) < top_n and (i < len(oversold_sorted) or i < len(breakout_sorted)):
        if i < len(oversold_sorted):
            ranked.append(oversold_sorted[i])
            if len(ranked) >= top_n:
                break
        if i < len(breakout_sorted):
            ranked.append(breakout_sorted[i])
        i += 1

    return ranked[:top_n]


def run_pipeline(universe_limit: int = 100, rsi_threshold: float = 35.0, top_n: int = 10) -> Dict:
    GUARD.reset()
    symbols = get_sp500_universe.invoke({"limit": universe_limit})

    snapshots: List[Dict] = []
    for symbol in symbols:
        snap = get_ticker_snapshot.invoke({"symbol": symbol, "lookback_days": 260})
        if snap:
            snapshots.append(snap)

    candidates = screen_for_setups.invoke({"snapshots": snapshots, "rsi_threshold": rsi_threshold})
    ideas = generate_trade_ideas.invoke({"candidates": candidates})
    ranked = rank_trade_ideas.invoke({"ideas": ideas, "top_n": top_n})

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "trade_ideas": ranked,
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
