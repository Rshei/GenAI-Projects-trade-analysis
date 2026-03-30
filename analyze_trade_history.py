from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


def load_reports() -> List[Dict]:
    reports_dir = Path("results/comparisons")
    if not reports_dir.exists():
        return []

    reports: List[Dict] = []
    for path in sorted(reports_dir.glob("comparison_*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            data["_source_file"] = str(path)
            reports.append(data)
    return reports


def select_latest_per_snapshot(reports: List[Dict]) -> List[Dict]:
    latest: Dict[str, Dict] = {}

    for r in reports:
        key = r.get("source_snapshot_as_of")
        if not key:
            continue
        existing = latest.get(key)
        if existing is None or r.get("evaluated_at", "") > existing.get("evaluated_at", ""):
            latest[key] = r

    return list(latest.values())


def summarize_frame(frame: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_cols + ["count", "average_return_pct", "win_rate_pct"])

    grouped = frame.groupby(group_cols, dropna=False)
    summary = grouped.agg(count=("return_pct", "size"), average_return_pct=("return_pct", "mean")).reset_index()

    wins = (
        frame.assign(is_win=frame["status"].isin(["target_hit", "open_profit"]))
        .groupby(group_cols, dropna=False)["is_win"]
        .mean()
        .reset_index(name="win_rate_pct")
    )
    summary = summary.merge(wins, on=group_cols, how="left")
    summary["average_return_pct"] = summary["average_return_pct"].round(2)
    summary["win_rate_pct"] = (summary["win_rate_pct"] * 100).round(2)
    return summary


def build_analytics(reports: List[Dict]) -> Dict:
    deduped = select_latest_per_snapshot(reports)

    current_rows = []
    horizon_rows = []
    recent_snapshots = []

    for report in deduped:
        evals = report.get("evaluations", [])

        per_snapshot_returns = []
        per_snapshot_wins = 0
        for e in evals:
            ret = float(e.get("current_return_pct", 0.0))
            status = str(e.get("status", ""))
            current_rows.append(
                {
                    "source_snapshot_as_of": report.get("source_snapshot_as_of"),
                    "symbol": e.get("symbol"),
                    "setup": e.get("setup"),
                    "return_pct": ret,
                    "status": status,
                }
            )
            per_snapshot_returns.append(ret)
            if status in {"target_hit", "open_profit"}:
                per_snapshot_wins += 1

            for horizon, hdata in e.get("horizons", {}).items():
                if hdata.get("return_pct") is None:
                    continue
                horizon_rows.append(
                    {
                        "source_snapshot_as_of": report.get("source_snapshot_as_of"),
                        "symbol": e.get("symbol"),
                        "setup": e.get("setup"),
                        "horizon": horizon,
                        "return_pct": float(hdata.get("return_pct", 0.0)),
                        "status": hdata.get("status", ""),
                    }
                )

        trade_count = len(evals)
        avg_ret = round(sum(per_snapshot_returns) / trade_count, 2) if trade_count else 0.0
        win_rate = round((per_snapshot_wins / trade_count) * 100, 2) if trade_count else 0.0
        recent_snapshots.append(
            {
                "source_snapshot_as_of": report.get("source_snapshot_as_of"),
                "evaluated_at": report.get("evaluated_at"),
                "trades": trade_count,
                "average_return_pct": avg_ret,
                "win_rate_pct": win_rate,
            }
        )

    current_df = pd.DataFrame(current_rows)
    horizon_df = pd.DataFrame(horizon_rows)

    trades_analyzed = len(current_df)
    current_avg_return = round(float(current_df["return_pct"].mean()), 2) if trades_analyzed else 0.0
    current_win_rate = (
        round(float(current_df["status"].isin(["target_hit", "open_profit"]).mean() * 100), 2)
        if trades_analyzed
        else 0.0
    )

    summary_by_setup_current = summarize_frame(current_df, ["setup"])
    summary_by_setup_horizon = summarize_frame(horizon_df, ["setup", "horizon"])
    summary_by_horizon = summarize_frame(horizon_df, ["horizon"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "snapshots_analyzed": len(deduped),
            "trades_analyzed": trades_analyzed,
            "current_average_return_pct": current_avg_return,
            "current_win_rate_pct": current_win_rate,
        },
        "recent_snapshots": recent_snapshots,
        "current_evaluations": current_df,
        "horizon_evaluations": horizon_df,
        "summary_by_setup_current": summary_by_setup_current,
        "summary_by_setup_horizon": summary_by_setup_horizon,
        "summary_by_horizon": summary_by_horizon,
    }


def save_analytics(analytics: Dict) -> None:
    out_dir = Path("results/analytics")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_json = {
        "generated_at": analytics.get("generated_at"),
        "overview": analytics.get("overview", {}),
        "recent_snapshots": analytics.get("recent_snapshots", []),
    }
    with (out_dir / "trade_history_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)

    analytics["current_evaluations"].to_csv(out_dir / "current_evaluations.csv", index=False)
    analytics["horizon_evaluations"].to_csv(out_dir / "horizon_evaluations.csv", index=False)
    analytics["summary_by_setup_current"].to_csv(out_dir / "summary_by_setup_current.csv", index=False)
    analytics["summary_by_setup_horizon"].to_csv(out_dir / "summary_by_setup_horizon.csv", index=False)
    analytics["summary_by_horizon"].to_csv(out_dir / "summary_by_horizon.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze aggregated trade comparison history")
    parser.parse_args()

    reports = load_reports()
    analytics = build_analytics(reports)
    save_analytics(analytics)
    print(
        json.dumps(
            {
                "generated_at": analytics["generated_at"],
                "overview": analytics["overview"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
