"""
Quick Start Guide for Advanced Trade Idea Screener

Run these commands to get started immediately.
"""

# ============================================================================
# INSTALLATION
# ============================================================================

"""
1. Install dependencies:
   pip install -r requirements.txt

2. (Optional) Train ML model on historical data:
   python ml_model.py
"""

# ============================================================================
# QUICKSTART - RUN THE APP
# ============================================================================

"""
Start the Streamlit interface:
   streamlit run streamlit_app.py

Then:
1. Go to "Run Screener" tab
2. Click "🚀 Run Trade Idea Pipeline"
3. Review the 10 top ideas
4. Go to "Evaluate Snapshot" to compare ideas to current prices
5. Check "Analytics" for historical performance
6. Use "Trade Tracker" to compare predictions vs. actual outcomes
"""

# ============================================================================
# QUICK EXAMPLES - Python Usage
# ============================================================================

# Example 1: Generate trade ideas with default settings
from trade_idea_agents import run_pipeline, save_results

result = run_pipeline(
    universe_limit=100,           # Scan 100 stocks
    rsi_threshold=35.0,           # Oversold threshold
    top_n=10,                     # Get top 10 ideas
    include_news=True             # Include news sentiment (slower)
)

saved = save_results(result)
print(f"Generated {len(result['trade_ideas'])} ideas")
print(f"Saved to {saved['json']}")


# Example 2: Evaluate a saved snapshot
from compare_trade_results import load_snapshot, build_report, save_report
from pathlib import Path

latest = Path("results/latest_trade_ideas.json")
snapshot = load_snapshot(latest)
report = build_report(snapshot)
saved = save_report(report, "latest_trade_ideas.json")

print(f"Average return: {report['current_summary']['average_return_pct']}%")
print(f"Win rate: {report['current_summary']['win_rate_pct']}%")


# Example 3: Build analytics from all comparisons
from analyze_trade_history import load_reports, build_analytics, save_analytics

reports = load_reports()
analytics = build_analytics(reports)
save_analytics(analytics)

print(f"Analyzed {analytics['overview']['snapshots_analyzed']} snapshots")
print(f"Overall win rate: {analytics['overview']['current_win_rate_pct']}%")


# Example 4: Track predicted vs. actual trade performance
from trade_tracker import TradeOutcomeTracker
import json

tracker = TradeOutcomeTracker()

# Add new ideas to tracking
with open("results/latest_trade_ideas.json") as f:
    latest = json.load(f)
    
added = tracker.add_trades(latest['trade_ideas'], "snapshot_1")
print(f"Added {len(added)} trades to tracker")

# Later, when trade closes:
tracker.update_trade_outcome(added[0], exit_price=120.50, dayshold=3)

# Get performance stats
stats = tracker.get_stats()
print(f"Win rate: {stats['win_rate_pct']}%")
print(f"Avg return: {stats['avg_return_pct']}%")
print(f"Prediction accuracy: {stats['prediction_accuracy']}")


# Example 5: Filter ideas by risk/reward and volatility
from trade_utils import (
    filter_ideas_by_risk_reward,
    filter_ideas_by_volatility,
    create_trade_plan
)

# Filter by minimum risk/reward ratio
filtered = filter_ideas_by_risk_reward(result['trade_ideas'], min_ratio=2.0)
print(f"After R:R filter: {len(filtered)} ideas (from {len(result['trade_ideas'])})")

# Filter by maximum volatility
filtered = filter_ideas_by_volatility(filtered, max_atr_pct=4.0)
print(f"After volatility filter: {len(filtered)} ideas")

# Create detailed trade plan
if filtered:
    plan = create_trade_plan(filtered[0], account_size=10000, risk_pct=2.0)
    print(f"Trade plan for {plan['symbol']}:")
    print(f"  Entry: {plan['entry']}")
    print(f"  Position size: {plan['position_size']} shares")
    print(f"  Risk/Reward: {plan['risk_reward_ratio']}")


# Example 6: Custom screener with MACD only
from trade_idea_agents import (
    get_sp500_universe,
    get_ticker_snapshot,
    screen_for_setups,
    generate_trade_ideas,
    rank_trade_ideas
)

# Get universe
symbols = get_sp500_universe(limit=50)

# Fetch snapshots
snapshots = []
for sym in symbols[:10]:  # Just 10 for speed
    snap = get_ticker_snapshot(sym)
    if snap:
        snapshots.append(snap)

# Screen (native filtering)
candidates = screen_for_setups(snapshots, rsi_threshold=35)

# Filter to MACD only
macd_only = [c for c in candidates if c.get('setup') == 'macd_bullish']

# Generate & rank
ideas = generate_trade_ideas(macd_only)
ranked = rank_trade_ideas(ideas, top_n=5)

print(f"Found {len(ranked)} MACD bullish setups")


# Example 7: Train ML model on historical data
from ml_model import train_model, save_model, score_ideas_with_model

# Train
model = train_model()
if model:
    save_model(model)
    
    # Use it to score ideas
    scored = score_ideas_with_model(result['trade_ideas'], model)
    print(f"ML scores added! Sample: {scored[0]['ml_score']}")


# ============================================================================
# COMMON TASKS
# ============================================================================

"""
TASK: Screen only large-cap stocks with strong uptrend
-------
from trade_idea_agents import run_pipeline
from trade_utils import filter_ideas_by_risk_reward

result = run_pipeline(universe_limit=200)

# Filter
large_cap = [i for i in result['trade_ideas'] if i['market_cap'] > 50e9]
good_ratio = filter_ideas_by_risk_reward(large_cap, min_ratio=2.0)

print(f"FinalCount: {len(good_ratio)} large-cap ideas with 2:1+ risk/reward")
"""

"""
TASK: Compare this week's ideas vs. last week's
-------
from pathlib import Path
from compare_trade_results import load_snapshot, build_report

# Find snapshots
snapshots = sorted(Path("results").glob("trade_ideas_*.json"), reverse=True)
this_week = snapshots[0]
last_week = snapshots[7] if len(snapshots) > 7 else snapshots[0]

# Compare
report_current = build_report(load_snapshot(this_week))
report_previous = build_report(load_snapshot(last_week))

print(f"This week win rate: {report_current['current_summary']['win_rate_pct']}%")
print(f"Last week win rate: {report_previous['current_summary']['win_rate_pct']}%")
"""

"""
TASK: Export ideas to CSV for spreadsheet
-------
import pandas as pd
from trade_idea_agents import run_pipeline

result = run_pipeline()
df = pd.DataFrame(result['trade_ideas'])
df.to_csv("my_trade_ideas.csv", index=False)
print("Exported to my_trade_ideas.csv")
"""

"""
TASK: Find best performing setup
-------
from trade_tracker import TradeOutcomeTracker

tracker = TradeOutcomeTracker()
perf = tracker.get_performance_by_setup()

best = perf.loc[perf['win_rate_pct'].idxmax()]
print(f"Best setup: {best['setup']} with {best['win_rate_pct']}% win rate")
"""

# ============================================================================
# CONFIGURATION TIPS
# ============================================================================

"""
Tune these settings in config.py:

1. SCREENING:
   - MIN_MARKET_CAP: Raise for larger stocks only
   - RSI_OVERSOLD_THRESHOLD: Lower (30) = more sensitive
   
2. SCORING:
   - SCORE_WEIGHTS: Adjust technical/ML/sentiment mix
   - MIN_RISK_REWARD_RATIO: Raise for quality ideas
   
3. ML:
   - Use ML_MODEL_MIN_ACCURACY to only use model if proven
   
4. NEWS:
   - Toggle FEATURE_NEWS_SENTIMENT on/off (slower with on)
   
5. TRACKING:
   - SUCCESS_MIN_RETURN: Define what counts as a "win"
"""

# ============================================================================
# NEXT STEPS
# ============================================================================

"""
1. Run screener with news sentiment on (slower but better)
2. Let ideas run through their holding periods
3. Update outcomes in Trade Tracker
4. Check prediction accuracy in Trade Tracker tab
5. Adjust config.py based on what works
6. Train ML model with more historical data
7. Measure improvement over time
"""

if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║      Advanced Trade Idea Screener - Quick Start Guide          ║
    ╠════════════════════════════════════════════════════════════════╣
    ║                                                                ║
    ║  START HERE:                                                  ║
    ║  $ streamlit run streamlit_app.py                             ║
    ║                                                                ║
    ║  Key Features:                                                ║
    ║  ✓ 5 Technical Setups                                         ║
    ║  ✓ News & Sentiment Scoring                                   ║
    ║  ✓ Machine Learning Predictions                               ║
    ║  ✓ Trade Outcome Tracking                                     ║
    ║  ✓ Technical Utilities (Risk/Reward, Position Sizing)         ║
    ║                                                                ║
    ║  See examples above or check README.md for details            ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
