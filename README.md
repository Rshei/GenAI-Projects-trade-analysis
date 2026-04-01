# 📈 Advanced Trade Idea Screener & Analytics

A sophisticated stock screening and trade analytics platform that combines technical analysis, machine learning, and sentiment analysis to identify and evaluate trade opportunities.

## 🚀 Features

### 1. **Advanced Screening Engine**
   - **5 Technical Setups**:
     - Oversold RSI (Mean Reversion)
     - MA50 Breakout (Trend Continuation)
     - Swing Reversal (Support Bounces)
     - MACD Bullish Crossover (Momentum)
     - Bollinger Band Bounce (Volatility Reversion)
   
   - **Dynamic Filters**:
     - Market cap minimum ($1B+)
     - Volume profile scoring
     - ATR-based stop losses (risk-adjusted)
     - Bollinger Band positioning
     - MACD signal confirmation
   
   - **Customizable Parameters**:
     - Universe size (20-500 stocks)
     - RSI threshold (10-50)
     - Number of top ideas to select

### 2. **News & Sentiment Scoring**
   - Real-time news buzz detection
   - Headline sentiment analysis
   - Sentiment-weighted idea ranking
   - News count as engagement metric

### 3. **Machine Learning Model**
   - RandomForest predictor trained on historical outcomes
   - Features: RSI, volume score, market cap, MACD signal
   - Success probability scoring
   - Blended composite scoring (technical + ML)
   - Can be improved iteratively with more trade outcomes

### 4. **Trade Outcome Tracking**
   - Compare predicted performance to actual results
   - Per-setup performance analytics
   - Prediction accuracy metrics
   - Historical trade database
   - Win rate and return analysis

### 5. **Comprehensive Analytics**
   - Performance by trading setup
   - Performance by time horizon (1d, 3d, 1w, 1m)
   - Recent snapshot tracking
   - Aggregate statistics and trends
   - Historical comparison reports

### 6. **Professional Trade Planning**
   - Risk/reward ratio calculation
   - Position sizing based on account risk
   - Volatility-adjusted stops
   - Trend strength identification
   - Exportable trade plans

---

## 📚 Architecture

```
trade_idea_agents.py
├─ get_sp500_universe()        # Fetch S&P 500 symbols
├─ get_ticker_snapshot()       # Compute indicators (RSI, MA50, MA200, ATR, MACD, BB)
├─ screen_for_setups()         # 5 technical patterns
├─ generate_trade_ideas()      # Structured ideas with rationales
├─ rank_trade_ideas()          # Composite scoring
├─ get_news_sentiment()        # News & buzz analysis
└─ run_pipeline()              # Complete pipeline (returns top N ideas)

compare_trade_results.py
├─ build_report()              # Evaluate snapshot vs. current prices
├─ classify_trade()            # Status: target_hit, stop_hit, open_profit, open_loss
└─ save_report()               # JSON + CSV reports per snapshot

analyze_trade_history.py
├─ load_reports()              # Load all comparisons
├─ build_analytics()           # Aggregate stats by setup/horizon
├─ save_analytics()            # JSON summary + CSVs
└─ summarize_frame()           # Groupby win rate / avg return

trade_tracker.py
├─ TradeOutcomeTracker         # Database of predicted & actual trades
├─ create_tracked_trade()      # Convert idea → tracked trade
├─ update_trade_outcome()      # Record exit price & status
├─ get_stats()                 # Aggregate performance metrics
└─ get_performance_by_setup()  # Setup-level analytics

ml_model.py
├─ train_model()               # RandomForest on historical data
├─ save_model()                # Persist to disk
├─ load_model()                # Load for scoring
└─ score_ideas_with_model()    # Apply ML to new ideas

trade_utils.py
├─ calculate_risk_reward_ratio()
├─ calculate_position_size()
├─ filter_ideas_by_risk_reward()
├─ filter_ideas_by_volatility()
├─ create_trade_plan()
└─ export_trades_to_csv()

streamlit_app.py
├─ Tab 1: Run Screener         # Generate new ideas
├─ Tab 2: Evaluate Snapshot    # Compare to current prices
├─ Tab 3: Analytics            # View historical performance
└─ Tab 4: Trade Tracker        # Track predicted vs. actual
```

---

## 🛠️ Installation

```bash
# Clone repository
git clone <repo>
cd GenAI-Projects-trade-analysis

# Install dependencies
pip install -r requirements.txt

# (Optional) Train ML model on historical data
python ml_model.py
```

---

## 📖 Usage

### Run the Streamlit App
```bash
streamlit run streamlit_app.py
```

### Generate Trade Ideas
```bash
# Run screener with custom parameters
python trade_idea_agents.py
```

### Evaluate a Snapshot
```bash
# Compare historical ideas to current prices
python compare_trade_results.py --snapshot results/latest_trade_ideas.json
```

### Build Analytics
```bash
# Aggregate all comparison reports
python analyze_trade_history.py
```

### Train ML Model
```bash
# Improve predictions with historical outcomes
python ml_model.py
```

---

## 📊 Output Structure

```
results/
├── trade_ideas_<timestamp>.json      # Raw screener snapshots
├── latest_trade_ideas.json           # Latest snapshot copy
├── latest_trade_ideas.csv
├── trades_db.json                    # Tracked trades (predicted vs. actual)
│
├── comparisons/
│   ├── comparison_<timestamp>.json   # Evaluation report
│   ├── comparison_<timestamp>.csv
│   ├── latest_comparison.json
│   └── latest_comparison.csv
│
├── analytics/
│   ├── trade_history_summary.json
│   ├── current_evaluations.csv
│   ├── horizon_evaluations.csv
│   ├── summary_by_setup_current.csv
│   ├── summary_by_setup_horizon.csv
│   ├── summary_by_horizon.csv
│   └── trade_dashboard.html
│
└── models/
    ├── ml_predictor.pkl              # Trained RandomForest
    └── scaler.pkl

```

---

## 🎯 Trade Setups Explained

### 1. **Oversold RSI** (Mean Reversion)
- RSI14 below configurable threshold (default: 35)
- Historically mean-reverts upward
- Best for momentum bounce trades

### 2. **MA50 Breakout** (Trend Continuation)
- Price crosses above 50-day moving average
- Indicates trend shift to upside
- Often leads to continuation moves

### 3. **Swing Reversal** (Support Trade)
- Price pulled back near MA50 but above MA200
- MA50 is rising (uptrend established)
- High probability pullback bounce
- Popular for swing traders

### 4. **MACD Bullish** (Momentum)
- MACD line crosses above signal line
- RSI > 40 (confirming momentum)
- Early momentum detection

### 5. **Bollinger Band Bounce** (Mean Reversion)
- Price within 15% of lower Bollinger Band
- Statistical mean reversion setup
- Works well in ranging markets

---

## 📈 Scoring System

Each trade idea receives multiple scores:

1. **Technical Score** (60% weight)
   - Setup-specific scoring
   - RSI depth (oversold only)
   - Volume confirmation
   - Market cap stability bonus

2. **ML Score** (20% weight)
   - RandomForest prediction
   - Trained on historical outcomes
   - Learns pattern success rates

3. **Sentiment Score** (20% weight)
   - News buzz (0-1)
   - Headline sentiment (-1 to +1)
   - Recent news count

**Final Score** = 0.6 × Technical + 0.2 × ML + 0.2 × Sentiment

---

## 📊 Key Metrics

### Trade Idea Metrics
- **Risk/Reward Ratio**: (TP - Entry) / (Entry - SL)
- **Win Rate**: % of trades hitting target vs. stop
- **Avg Return**: Average % return across trades
- **Prediction Accuracy**: Correlation between predicted & actual scores

### Setup Performance
- Grouped by technical pattern
- Win rate by setup
- Average return by setup
- Trade count per setup

### Horizon Performance
- 1-day return profile
- 3-day return profile
- 1-week return profile
- 1-month return profile

---

## 🔧 Customization

### Add New Technical Indicator
```python
# In trade_idea_agents.py, add to get_ticker_snapshot():
def compute_custom_indicator(close_series):
    # Your logic here
    pass

# Add to snapshot and screen_for_setups()
```

### Add New Setup Pattern
```python
# In screen_for_setups():
if condition_for_new_setup:
    row = dict(snap)
    row["setup"] = "new_setup_name"
    candidates.append(row)
```

### Adjust Scoring Weights
```python
# In rank_trade_ideas(), modify composite_score calculation:
idea["composite_score"] = min(1.0, 
    setup_score * 0.5 +      # Increase setup weight
    vol_bonus * 0.2 +
    market_cap * 0.1
)
```

---

## ⚠️ Disclaimer

**This tool is for educational and research purposes only.**

- Past performance does not guarantee future results
- All trading involves significant risk
- Use proper position sizing and risk management
- Validate signals with your own analysis
- Paper trade before risking real capital

---

## 📝 Recent Improvements

✅ **5 Technical Setups** - Expanded from 2 to diverse patterns
✅ **Advanced Indicators** - ATR, MACD, Bollinger Bands
✅ **ML Scoring** - RandomForest trained on outcomes
✅ **News Sentiment** - Buzz detection & headline analysis
✅ **Trade Tracker** - Compare predictions vs. actual results
✅ **Professional UX** - Emojis, metrics, formatted output
✅ **Comprehensive Utils** - Risk/reward, position sizing, filtering

---

## 🚀 Future Enhancements

- [ ] Backtesting engine for strategy validation
- [ ] Real-time alerting for new setups
- [ ] Portfolio management & correlation analysis
- [ ] Options strategy recommendations
- [ ] Institutional-grade risk metrics
- [ ] API integration (webhook alerts, trading bot)
- [ ] Statistical edge validation
- [ ] Advanced ML models (LSTM, transformer)

---

## 📧 Questions?

Review the code, experiment with parameters, and use the Trade Tracker to validate your improvements!

**Happy trading!** 📊📈
