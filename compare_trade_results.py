from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf


HOLDING_PERIODS = {"1d": 1, "3d": 3, "1w": 5, "1m": 21}


def load_snapshot(path: str | Path) -> Dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def get_trade_history(symbol: str, snapshot_time: datetime) -> pd.DataFrame:
    start = (snapshot_time - timedelta(days=14)).date().isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=5)).date().isoformat()

    history = yf.download(
        symbol,
        start=start,
        end=end,
        auto_adjust=False,
        progress=False,
    )

    if history is None or history.empty:
        return pd.DataFrame(columns=["Close"])

    if isinstance(history.columns, pd.MultiIndex):
        history.columns = history.columns.get_level_values(0)

    if "Close" not in history.columns:
        return pd.DataFrame(columns=["Close"])

    out = history[["Close"]].copy().dropna()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out


def locate_entry_position(history: pd.DataFrame, snapshot_time: datetime) -> Optional[int]:
    if history.empty:
        return None

    snap_day = pd.Timestamp(snapshot_time).tz_localize(None).normalize()
    idx_days = history.index.normalize()

    le_mask = idx_days <= snap_day
    if le_mask.any():
        return int(le_mask.nonzero()[0][-1])

    ge_mask = idx_days >= snap_day
    if ge_mask.any():
        return int(ge_mask.nonzero()[0][0])

    return None


def classify_trade(current_price: float, entry: float, stop_loss: float, take_profit: float) -> str:
    if current_price <= stop_loss:
        return "stop_hit"
    if current_price >= take_profit:
        return "target_hit"
    if current_price > entry:
        return "open_profit"
    if current_price < entry:
        return "open_loss"
    return "flat"


def classify_path(
    path_prices: List[float],
    final_price: float,
    entry: float,
    stop_loss: float,
    take_profit: float,
) -> str:
    for price in path_prices:
        if price <= stop_loss:
            return "stop_hit"
        if price >= take_profit:
            return "target_hit"

    return classify_trade(final_price, entry, stop_loss, take_profit)


def summarize_rows(rows: List[Dict]) -> Dict:
    if not rows:
        return {
            "count": 0,
            "average_return_pct": 0.0,
            "win_rate_pct": 0.0,
            "status_counts": {},
        }

    returns = [float(r["return_pct"]) for r in rows]
    statuses = [str(r["status"]) for r in rows]
    counts = Counter(statuses)
    wins = counts.get("target_hit", 0) + counts.get("open_profit", 0)

    return {
        "count": len(rows),
        "average_return_pct": round(sum(returns) / len(returns), 2),
        "win_rate_pct": round((wins / len(rows)) * 100, 2),
        "status_counts": dict(counts),
    }


def build_report(snapshot: Dict) -> Dict:
    snapshot_time = datetime.fromisoformat(snapshot["as_of"])

    evaluations: List[Dict] = []
    current_rows: List[Dict] = []
    horizon_rows: List[Dict] = []

    for idea in snapshot.get("trade_ideas", []):
        symbol = str(idea["symbol"])
        entry = float(idea["entry"])
        stop_loss = float(idea["stop_loss"])
        take_profit = float(idea["take_profit"])

        history = get_trade_history(symbol, snapshot_time)
        entry_pos = locate_entry_position(history, snapshot_time)
        if entry_pos is None:
            continue

        closes = history["Close"].astype(float).tolist()
        current_price = float(closes[-1])
        current_return_pct = ((current_price - entry) / entry) * 100
        current_status = classify_trade(current_price, entry, stop_loss, take_profit)

        horizons: Dict[str, Dict] = {}
        for horizon, offset in HOLDING_PERIODS.items():
            target_pos = entry_pos + offset
            if target_pos >= len(closes):
                horizons[horizon] = {"price": None, "return_pct": None, "status": "insufficient_data"}
                continue

            final_price = float(closes[target_pos])
            path_prices = [float(p) for p in closes[entry_pos + 1 : target_pos + 1]]
            status = classify_path(path_prices, final_price, entry, stop_loss, take_profit)
            return_pct = ((final_price - entry) / entry) * 100

            horizons[horizon] = {
                "price": round(final_price, 4),
                "return_pct": round(return_pct, 4),
                "status": status,
            }

            horizon_rows.append(
                {
                    "symbol": symbol,
                    "setup": idea.get("setup", ""),
                    "horizon": horizon,
                    "return_pct": float(return_pct),
                    "status": status,
                }
            )

        evaluation = {
            "symbol": symbol,
            "setup": idea.get("setup", ""),
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "current_price": round(current_price, 4),
            "current_return_pct": round(current_return_pct, 4),
            "status": current_status,
            "horizons": horizons,
        }
        evaluations.append(evaluation)

        current_rows.append(
            {
                "symbol": symbol,
                "setup": idea.get("setup", ""),
                "return_pct": float(current_return_pct),
                "status": current_status,
            }
        )

    horizon_summary = {h: summarize_rows([r for r in horizon_rows if r["horizon"] == h]) for h in HOLDING_PERIODS}

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot_as_of": snapshot.get("as_of"),
        "symbols_evaluated": len(evaluations),
        "current_summary": summarize_rows(current_rows),
        "horizon_summary": horizon_summary,
        "evaluations": evaluations,
    }


def save_report(report: Dict, source_filename: str) -> Dict[str, str]:
    out_dir = Path("results/comparisons")
    out_dir.mkdir(parents=True, exist_ok=True)

    base = Path(source_filename).stem
    eval_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_json = out_dir / f"comparison_{base}_{eval_ts}.json"
    report_csv = out_dir / f"comparison_{base}_{eval_ts}.csv"
    latest_json = out_dir / "latest_comparison.json"
    latest_csv = out_dir / "latest_comparison.csv"

    with report_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with latest_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    flat_rows = []
    for e in report.get("evaluations", []):
        row = {
            "symbol": e.get("symbol"),
            "setup": e.get("setup"),
            "entry": e.get("entry"),
            "stop_loss": e.get("stop_loss"),
            "take_profit": e.get("take_profit"),
            "current_price": e.get("current_price"),
            "return_pct": e.get("current_return_pct"),
            "status": e.get("status"),
        }
        horizons = e.get("horizons", {})
        for h in HOLDING_PERIODS:
            row[f"{h}_price"] = horizons.get(h, {}).get("price")
            row[f"{h}_return_pct"] = horizons.get(h, {}).get("return_pct")
            row[f"{h}_status"] = horizons.get(h, {}).get("status")
        flat_rows.append(row)

    pd.DataFrame(flat_rows).to_csv(report_csv, index=False)
    pd.DataFrame(flat_rows).to_csv(latest_csv, index=False)

    return {
        "json": str(report_json),
        "csv": str(report_csv),
        "latest_json": str(latest_json),
        "latest_csv": str(latest_csv),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare saved trade ideas to market outcomes")
    parser.add_argument(
        "--snapshot",
        default="results/latest_trade_ideas.json",
        help="Path to trade idea snapshot JSON",
    )
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    snapshot = load_snapshot(snapshot_path)
    report = build_report(snapshot)
    saved = save_report(report, snapshot_path.name)
    print(json.dumps({"report": report, "saved": saved}, indent=2))


if __name__ == "__main__":
    main()
