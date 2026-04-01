from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

from analyze_trade_history import build_analytics, load_reports, save_analytics
from compare_trade_results import build_report, load_snapshot, save_report
from trade_idea_agents import run_pipeline, save_results
from trade_tracker import TradeOutcomeTracker


st.set_page_config(page_title="Trade Idea Screener", layout="wide")
st.title("📈 Trade Idea Screener & Analytics")


def list_snapshots() -> List[Path]:
    return sorted(Path("results").glob("trade_ideas_*.json"), reverse=True)


def list_comparisons() -> List[Path]:
    return sorted(Path("results/comparisons").glob("comparison_*.json"), reverse=True)


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def format_idea_dataframe(ideas: List[Dict]) -> pd.DataFrame:
    """Format trade ideas for display."""
    if not ideas:
        return pd.DataFrame()
    
    rows = []
    for idea in ideas:
        rows.append({
            "Symbol": idea.get("symbol", "N/A"),
            "Setup": idea.get("setup", "N/A"),
            "Entry": f"${idea.get('entry', 0):.2f}",
            "Stop Loss": f"${idea.get('stop_loss', 0):.2f}",
            "Target": f"${idea.get('take_profit', 0):.2f}",
            "Risk/Reward": f"{((idea.get('take_profit', 0) - idea.get('entry', 0)) / (idea.get('entry', 0) - idea.get('stop_loss', 0)) if idea.get('entry', 0) != idea.get('stop_loss', 0) else 0):.2f}",
            "Score": f"{idea.get('composite_score', idea.get('final_score', 0.5)) * 100:.0f}%",
            "Volume": f"{idea.get('volume_score', 0.5) * 100:.0f}%",
            "News": idea.get("buzz_score", "N/A"),
            "Rationale": idea.get("rationale", "N/A")[:60] + "...",
        })
    
    return pd.DataFrame(rows)


tabs = st.tabs(["🚀 Run Screener", "📊 Evaluate Snapshot", "📈 Analytics", "🎯 Trade Tracker"])


# ============================================================================
# TAB 1: RUN SCREENER
# ============================================================================
with tabs[0]:
    st.subheader("Configure Screener Parameters")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        universe_limit = st.slider("Universe Size", min_value=20, max_value=500, value=100, help="# of stocks to scan")
    with col2:
        rsi_threshold = st.slider("RSI Threshold", min_value=10.0, max_value=50.0, value=35.0, step=0.5, help="Oversold level")
    with col3:
        top_ideas = st.slider("Top Ideas", min_value=1, max_value=50, value=10)
    
    include_news = st.checkbox("Include News Sentiment", value=True, help="Add news buzz scoring (slower)")
    
    if st.button("🚀 Run Trade Idea Pipeline", type="primary", use_container_width=True):
        with st.spinner("Scanning universe and generating trade ideas..."):
            result = run_pipeline(
                universe_limit=universe_limit,
                rsi_threshold=rsi_threshold,
                top_n=top_ideas,
                include_news=include_news
            )
            saved_paths = save_results(result)
            st.session_state["pipeline_result"] = result
            st.session_state["pipeline_saved_paths"] = saved_paths
            st.success("✅ Screening complete!")

    result = st.session_state.get("pipeline_result")
    if result:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Symbols Scanned", result.get("symbols_screened", 0))
        col2.metric("Setups Found", result.get("setups_found", 0))
        col3.metric("Selected Ideas", len(result.get("trade_ideas", [])))
        col4.metric("Generated At", str(result.get("as_of", ""))[:10])
        
        # Display ideas
        st.subheader("🎯 Top Trade Ideas")
        ideas_df = format_idea_dataframe(result.get("trade_ideas", []))
        if not ideas_df.empty:
            st.dataframe(ideas_df, use_container_width=True, height=400)
        else:
            st.info("No trade ideas found with current parameters.")


# ============================================================================
# TAB 2: EVALUATE SNAPSHOT
# ============================================================================
with tabs[1]:
    st.subheader("Evaluate Trade Snapshot Performance")
    
    snapshots = list_snapshots()
    snapshot_options = [str(p.name) for p in snapshots]

    if snapshot_options:
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_name = st.selectbox("Select snapshot to evaluate:", snapshot_options)
            selected_path = [p for p in snapshots if p.name == selected_name][0]
        
        with col2:
            if st.button("📊 Evaluate", use_container_width=True):
                with st.spinner("Evaluating snapshot against current prices..."):
                    snapshot = load_snapshot(str(selected_path))
                    report = build_report(snapshot)
                    saved = save_report(report, selected_path.name)
                    st.session_state["comparison_report"] = report
                    st.session_state["comparison_saved_paths"] = saved
                    st.success("✅ Evaluation complete!")

    if st.button("Load Latest Comparison", use_container_width=True):
        latest = Path("results/comparisons/latest_comparison.json")
        if latest.exists():
            with st.spinner("Loading..."):
                st.session_state["comparison_report"] = load_json(latest)
                st.success("✅ Loaded!")
        else:
            st.warning("No latest comparison found.")

    report = st.session_state.get("comparison_report")
    if report:
        # Summary metrics
        current_sum = report.get("current_summary", {})
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Symbols Evaluated", report.get("symbols_evaluated", 0))
        col2.metric("Avg Return", f"{current_sum.get('average_return_pct', 0):.2f}%")
        col3.metric("Win Rate", f"{current_sum.get('win_rate_pct', 0):.1f}%")
        col4.metric("Evaluated At", str(report.get("evaluated_at", ""))[:10])
        
        # Detailed trade results
        st.subheader("Trade Evaluations")
        rows = []
        for e in report.get("evaluations", []):
            row = {
                "Symbol": e.get("symbol"),
                "Setup": e.get("setup"),
                "Entry": f"${e.get('entry', 0):.2f}",
                "Current": f"${e.get('current_price', 0):.2f}",
                "Return": f"{e.get('current_return_pct', 0):.2f}%",
                "Status": e.get("status", "N/A"),
            }
            rows.append(row)
        
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=400)
        
        # Horizon summary
        st.subheader("Horizon Performance")
        horizon_sum = report.get("horizon_summary", {})
        horizon_rows = []
        for horizon, data in horizon_sum.items():
            horizon_rows.append({
                "Horizon": horizon.upper(),
                "Avg Return": f"{data.get('average_return_pct', 0):.2f}%",
                "Win Rate": f"{data.get('win_rate_pct', 0):.1f}%",
                "Trades": data.get("count", 0),
            })
        
        st.dataframe(pd.DataFrame(horizon_rows), use_container_width=True)


# ============================================================================
# TAB 3: ANALYTICS
# ============================================================================
with tabs[2]:
    st.subheader("Historical Analytics & Performance Trends")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh Analytics", use_container_width=True):
            with st.spinner("Building analytics from all reports..."):
                reports = load_reports()
                analytics = build_analytics(reports)
                save_analytics(analytics)
                st.session_state["analytics_summary"] = {
                    "generated_at": analytics.get("generated_at"),
                    "overview": analytics.get("overview", {}),
                    "recent_snapshots": analytics.get("recent_snapshots", []),
                }
                st.success("✅ Analytics refreshed!")
    
    with col2:
        if st.button("📂 Load Analytics", use_container_width=True):
            summary_file = Path("results/analytics/trade_history_summary.json")
            if summary_file.exists():
                with st.spinner("Loading..."):
                    st.session_state["analytics_summary"] = load_json(summary_file)
                    st.success("✅ Loaded!")
            else:
                st.warning("No analytics found yet.")

    summary = st.session_state.get("analytics_summary")
    if summary:
        overview = summary.get("overview", {})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Snapshots Analyzed", overview.get("snapshots_analyzed", 0))
        c2.metric("Total Trades", overview.get("trades_analyzed", 0))
        c3.metric("Avg Return %", f"{overview.get('current_average_return_pct', 0):.2f}%")
        c4.metric("Win Rate %", f"{overview.get('current_win_rate_pct', 0):.1f}%")

        # Recent snapshots
        recent = pd.DataFrame(summary.get("recent_snapshots", []))
        if not recent.empty:
            st.subheader("Recent Snapshot Performance")
            st.dataframe(recent, use_container_width=True, height=300)

        # Performance by setup
        analytics_dir = Path("results/analytics")
        setup_current = analytics_dir / "summary_by_setup_current.csv"
        if setup_current.exists():
            st.subheader("Performance by Setup")
            st.dataframe(pd.read_csv(setup_current), use_container_width=True)

        # Performance by horizon
        by_horizon = analytics_dir / "summary_by_horizon.csv"
        if by_horizon.exists():
            st.subheader("Performance by Time Horizon")
            horizon_df = pd.read_csv(by_horizon)
            st.dataframe(horizon_df, use_container_width=True)
            if "horizon" in horizon_df.columns and "average_return_pct" in horizon_df.columns:
                st.bar_chart(horizon_df.set_index("horizon")["average_return_pct"])


# ============================================================================
# TAB 4: TRADE TRACKER
# ============================================================================
with tabs[3]:
    st.subheader("Track Predicted vs. Actual Trade Performance")
    
    tracker = TradeOutcomeTracker()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Add Latest Ideas to Tracker", use_container_width=True):
            latest_file = Path("results/latest_trade_ideas.json")
            if latest_file.exists():
                with open(latest_file) as f:
                    latest = json.load(f)
                ideas = latest.get("trade_ideas", [])
                if ideas:
                    added = tracker.add_trades(ideas, "latest_snapshot")
                    st.success(f"✅ Added {len(added)} trades to tracker!")
                else:
                    st.warning("No ideas in latest snapshot")
            else:
                st.warning("No latest snapshot found")
    
    # Stats
    stats = tracker.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tracked", stats["total_trades"])
    col2.metric("Closed", stats["closed_trades"])
    col3.metric("Open", stats["open_trades"])
    col4.metric("Win Rate", f"{stats['win_rate_pct']:.1f}%")
    
    if stats.get("prediction_accuracy"):
        st.metric("Prediction Accuracy", f"{stats['prediction_accuracy']:.3f}")
    
    # Trade table
    st.subheader("Tracked Trades")
    trades_df = tracker.get_trades_df()
    if not trades_df.empty:
        display_cols = ["symbol", "setup", "status", "entry_price", "exit_price", "actual_return_pct", "initial_score", "dayshold"]
        st.dataframe(trades_df[display_cols], use_container_width=True, height=400)
    else:
        st.info("No trades tracked yet. Add ideas from the screener!")
    
    # Performance by setup
    if stats["closed_trades"] > 0:
        st.subheader("Performance by Setup")
        perf_df = tracker.get_performance_by_setup()
        if not perf_df.empty:
            st.dataframe(perf_df, use_container_width=True)

