from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

from analyze_trade_history import build_analytics, load_reports, save_analytics
from compare_trade_results import build_report, load_snapshot, save_report
from trade_idea_agents import run_pipeline, save_results


st.set_page_config(page_title="Trade Idea Screener", layout="wide")
st.title("Trade Idea Screener & Analytics")


def list_snapshots() -> List[Path]:
    return sorted(Path("results").glob("trade_ideas_*.json"), reverse=True)


def list_comparisons() -> List[Path]:
    return sorted(Path("results/comparisons").glob("comparison_*.json"), reverse=True)


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


tabs = st.tabs(["Run Screener", "Evaluate Snapshot", "Analytics", "Saved Files"])


with tabs[0]:
    universe_limit = st.slider("Universe Limit", min_value=20, max_value=500, value=100)
    rsi_threshold = st.slider("RSI Threshold", min_value=10.0, max_value=50.0, value=35.0, step=0.5)
    top_ideas = st.slider("Top Ideas", min_value=1, max_value=50, value=10)

    if st.button("Run Trade Idea Pipeline", type="primary"):
        with st.spinner("Running screener pipeline..."):
            result = run_pipeline(universe_limit=universe_limit, rsi_threshold=rsi_threshold, top_n=top_ideas)
            saved_paths = save_results(result)
            st.session_state["pipeline_result"] = result
            st.session_state["pipeline_saved_paths"] = saved_paths

    result = st.session_state.get("pipeline_result")
    if result:
        st.subheader("Pipeline Summary")
        st.json(
            {
                "as_of": result.get("as_of"),
                "symbols_screened": result.get("symbols_screened"),
                "setups_found": result.get("setups_found"),
                "top_n": result.get("top_n"),
            }
        )
        st.dataframe(pd.DataFrame(result.get("trade_ideas", [])), use_container_width=True)

        saved_paths = st.session_state.get("pipeline_saved_paths", {})
        st.caption("Saved files")
        st.json(saved_paths)


with tabs[1]:
    snapshots = list_snapshots()
    snapshot_options = [str(p) for p in snapshots]

    if snapshot_options:
        selected = st.selectbox("Select trade snapshot", snapshot_options)

        if st.button("Run Comparison for Selected Snapshot"):
            with st.spinner("Evaluating selected snapshot..."):
                snapshot = load_snapshot(selected)
                report = build_report(snapshot)
                saved = save_report(report, Path(selected).name)
                st.session_state["comparison_report"] = report
                st.session_state["comparison_saved_paths"] = saved

    if st.button("Load Existing Latest Comparison"):
        latest = Path("results/comparisons/latest_comparison.json")
        if latest.exists():
            with st.spinner("Loading latest comparison..."):
                st.session_state["comparison_report"] = load_json(latest)
        else:
            st.warning("No latest comparison file found.")

    report = st.session_state.get("comparison_report")
    if report:
        st.subheader("Comparison Summary")
        st.json(
            {
                "evaluated_at": report.get("evaluated_at"),
                "source_snapshot_as_of": report.get("source_snapshot_as_of"),
                "symbols_evaluated": report.get("symbols_evaluated"),
                "current_summary": report.get("current_summary"),
                "horizon_summary": report.get("horizon_summary"),
            }
        )

        rows = []
        for e in report.get("evaluations", []):
            rows.append(
                {
                    "symbol": e.get("symbol"),
                    "setup": e.get("setup"),
                    "entry": e.get("entry"),
                    "current_price": e.get("current_price"),
                    "return_pct": e.get("current_return_pct"),
                    "status": e.get("status"),
                    "1d_status": e.get("horizons", {}).get("1d", {}).get("status"),
                    "3d_status": e.get("horizons", {}).get("3d", {}).get("status"),
                    "1w_status": e.get("horizons", {}).get("1w", {}).get("status"),
                    "1m_status": e.get("horizons", {}).get("1m", {}).get("status"),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        saved = st.session_state.get("comparison_saved_paths")
        if saved:
            st.caption("Saved comparison files")
            st.json(saved)
    elif not snapshot_options:
        st.info("No trade snapshots found yet. Run the screener first.")


with tabs[2]:
    if st.button("Refresh Analytics"):
        with st.spinner("Refreshing analytics from comparison reports..."):
            reports = load_reports()
            analytics = build_analytics(reports)
            save_analytics(analytics)
            st.session_state["analytics_summary"] = {
                "generated_at": analytics.get("generated_at"),
                "overview": analytics.get("overview", {}),
                "recent_snapshots": analytics.get("recent_snapshots", []),
            }

    if st.button("Load Current Analytics Files"):
        summary_file = Path("results/analytics/trade_history_summary.json")
        if summary_file.exists():
            with st.spinner("Loading analytics summary..."):
                st.session_state["analytics_summary"] = load_json(summary_file)
        else:
            st.warning("No analytics summary found.")

    summary = st.session_state.get("analytics_summary")
    if summary:
        overview = summary.get("overview", {})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Snapshots", overview.get("snapshots_analyzed", 0))
        c2.metric("Trades", overview.get("trades_analyzed", 0))
        c3.metric("Avg Return %", overview.get("current_average_return_pct", 0.0))
        c4.metric("Win Rate %", overview.get("current_win_rate_pct", 0.0))

        recent = pd.DataFrame(summary.get("recent_snapshots", []))
        if not recent.empty:
            st.subheader("Recent Snapshots")
            st.dataframe(recent, use_container_width=True)

        analytics_dir = Path("results/analytics")
        setup_current = analytics_dir / "summary_by_setup_current.csv"
        by_horizon = analytics_dir / "summary_by_horizon.csv"
        setup_horizon = analytics_dir / "summary_by_setup_horizon.csv"

        if setup_current.exists():
            st.subheader("Summary by Setup (Current)")
            st.dataframe(pd.read_csv(setup_current), use_container_width=True)

        if by_horizon.exists():
            st.subheader("Summary by Horizon")
            horizon_df = pd.read_csv(by_horizon)
            st.dataframe(horizon_df, use_container_width=True)
            if "horizon" in horizon_df.columns and "average_return_pct" in horizon_df.columns:
                st.bar_chart(horizon_df.set_index("horizon")["average_return_pct"])

        if setup_horizon.exists():
            st.subheader("Summary by Setup and Horizon")
            st.dataframe(pd.read_csv(setup_horizon), use_container_width=True)


with tabs[3]:
    st.subheader("Saved Snapshot Files")
    snapshots = list_snapshots()
    if snapshots:
        st.write([str(p) for p in snapshots])
    else:
        st.write("No snapshot files found.")

    st.subheader("Saved Comparison Files")
    comparisons = list_comparisons()
    if comparisons:
        st.write([str(p) for p in comparisons])
    else:
        st.write("No comparison files found.")

    latest_trade_ideas = Path("results/latest_trade_ideas.json")
    if latest_trade_ideas.exists():
        st.subheader("Latest Trade Ideas")
        data = load_json(latest_trade_ideas)
        st.dataframe(pd.DataFrame(data.get("trade_ideas", [])), use_container_width=True)
