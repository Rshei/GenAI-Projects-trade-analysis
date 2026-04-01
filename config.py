"""
Configuration settings for the trade screening system.
Centralized control for all parameters and thresholds.
"""

# ============================================================================
# SCREENER CONFIGURATION
# ============================================================================

# Market cap filter (stocks with market cap > this amount)
MIN_MARKET_CAP = 1_000_000_000  # $1 billion

# RSI settings
RSI_PERIOD = 14
RSI_OVERSOLD_THRESHOLD = 35.0  # Default threshold for "oversold" setup

# Moving averages
MA50_PERIOD = 50
MA200_PERIOD = 200

# ATR (Average True Range)
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 2.0  # Use 2x ATR for stop loss

# Bollinger Bands
BB_PERIOD = 20
BB_STD_DEV = 2.0
BB_BOUNCE_THRESHOLD = 0.15  # Price within 15% of lower band = bounce setup

# MACD
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ============================================================================
# RANKING & SCORING CONFIGURATION
# ============================================================================

# Setup-specific scores
SETUP_SCORES = {
    "oversold_rsi": 0.20,
    "ma50_breakout": 0.15,
    "swing_reversal": 0.18,
    "macd_bullish": 0.15,
    "bb_bounce": 0.12,
}

# Weighting for composite score
SCORE_WEIGHTS = {
    "technical": 0.60,     # Technical indicator score
    "volume": 0.15,        # Volume confirmation
    "market_cap": 0.05,    # Large cap stability bonus
    "ml": 0.10,            # ML model prediction
    "sentiment": 0.10,     # News sentiment
}

# ML Model threshold for using predictions
ML_MODEL_MIN_ACCURACY = 0.5  # Don't use ML if accuracy < this

# ============================================================================
# TRADE IDEAS CONFIGURATION
# ============================================================================

# Entry/exit multipliers (from current close price)
ENTRY_MULTIPLIER = 1.0      # Entry = current close
STOP_LOSS_MULTIPLIER = 0.95  # Stop = entry * 0.95
TAKE_PROFIT_MULTIPLIER = 1.15  # TP = entry * 1.15

# Risk/reward filtering
MIN_RISK_REWARD_RATIO = 1.5  # Filter out ideas with RR < this
MAX_ATR_PCT_VOLATILITY = 5.0  # Filter out ideas with volatility > 5% of price

# ============================================================================
# NEWS & SENTIMENT CONFIGURATION
# ============================================================================

# News buzz scoring
MAX_NEWS_FOR_BUZZ_1 = 20  # # of articles for buzz score = 1.0
NEWS_POSITIVE_WORDS = [
    "surge", "gain", "rally", "beat", "strong", "upbeat", "upgrade",
    "bullish", "breakout", "surge", "pump", "higher", "boom", "soar",
]
NEWS_NEGATIVE_WORDS = [
    "fall", "decline", "drop", "miss", "weak", "downgrade", "bearish",
    "crash", "dump", "lower", "slump", "tumble", "collapse",
]

# ============================================================================
# MACHINE LEARNING CONFIGURATION
# ============================================================================

# RandomForest hyperparameters
RF_N_ESTIMATORS = 50
RF_MAX_DEPTH = 10
RF_RANDOM_STATE = 42
RF_N_JOBS = -1  # Use all cores

# Training data split
TEST_SPLIT = 0.2
TRAIN_RANDOM_STATE = 42

# Success target definition
SUCCESS_MIN_RETURN = 5.0  # Consider trade a "win" if return >= 5%

# ============================================================================
# TRADE TRACKING CONFIGURATION
# ============================================================================

# Trade status definitions
TRADE_STATUS_OPEN = "open"
TRADE_STATUS_WIN = "closed_win"
TRADE_STATUS_LOSS = "closed_loss"
TRADE_STATUS_TARGET = "closed_target"
TRADE_STATUS_STOP = "closed_stop"

# Closing criteria
HOLD_PERIODS = {
    "1d": 1,    # 1 trading day
    "3d": 3,    # 3 trading days
    "1w": 5,    # 1 week (5 trading days)
    "1m": 21,   # 1 month (21 trading days)
}

# ============================================================================
# ANALYTICS CONFIGURATION
# ============================================================================

# Aggregate window for "recent" snapshots
RECENT_SNAPSHOTS_COUNT = 10

# Performance tracking by dimension
GROUP_BY_SETUP = True
GROUP_BY_HORIZON = True
GROUP_BY_SETUP_HORIZON = True

# ============================================================================
# PIPELINE CONFIGURATION
# ============================================================================

# Default run parameters
DEFAULT_UNIVERSE_LIMIT = 100
DEFAULT_RSI_THRESHOLD = 35.0
DEFAULT_TOP_N_IDEAS = 10
DEFAULT_INCLUDE_NEWS = True

# Maximum tool calls guard
MAX_TOOL_CALLS = 500

# ============================================================================
# DATA OUTPUT CONFIGURATION
# ============================================================================

# Data directory paths
RESULTS_DIR = "results"
COMPARISONS_DIR = "results/comparisons"
ANALYTICS_DIR = "results/analytics"
MODELS_DIR = "models"

# JSON formatting
JSON_INDENT = 2

# CSV settings
CSV_INDEX = False
CSV_ENCODING = "utf-8"

# ============================================================================
# STREAMLIT APP CONFIGURATION
# ============================================================================

# Page settings
PAGE_TITLE = "Trade Idea Screener"
PAGE_LAYOUT = "wide"
INITIAL_SIDEBAR_STATE = "expanded"

# Update intervals (in seconds)
REFRESH_INTERVAL_DEFAULT = 300  # 5 minutes

# Display limits
MAX_ROWS_IN_TABLE = 500
CHART_HEIGHT = 400

# ============================================================================
# SAFETY & RISK MANAGEMENT
# ============================================================================

# Position sizing recommendations
MAX_ACCOUNT_RISK_PER_TRADE = 2.0  # Risk % of account per trade
MAX_TRADES_SAME_DAY = 5
MAX_CORRELATION_ALLOWED = 0.8  # Max correlation between open positions

# Drawdown limits
MAX_DAILY_LOSS = 2.0  # % of account
MAX_WEEKLY_LOSS = 5.0  # % of account
MAX_MONTHLY_LOSS = 10.0  # % of account

# ============================================================================
# FILTERS & CRITERIA
# ============================================================================

# Sector/industry filtering (if needed)
EXCLUDED_SECTORS = []

# Excluded symbols (thinly traded, penny stocks, etc)
EXCLUDED_SYMBOLS = ["BRK-A"]  # Berkshire Hathaway A shares (too expensive)

# Penny stock filter
PENNY_STOCK_THRESHOLD = 1.0  # Filter out stocks < $1

# ============================================================================
# EXPERIMENTAL / ADVANCED SETTINGS
# ============================================================================

# Use ensemble voting for final score
USE_ENSEMBLE_VOTING = False

# Use advanced position sizing (Kelly Criterion)
USE_KELLY_CRITERION = False

# Liquidity filter (minimum avg daily volume)
MIN_AVG_DAILY_VOLUME = 1_000_000

# Allow short setups (not implemented yet)
ALLOW_SHORT_SETUPS = False

# ============================================================================
# FEATURE FLAGS
# ============================================================================

FEATURE_MACD_SIGNAL = True
FEATURE_BOLLINGER_BANDS = True
FEATURE_ATR_STOPS = True
FEATURE_NEWS_SENTIMENT = True
FEATURE_ML_SCORING = True
FEATURE_TRADE_TRACKING = True
FEATURE_PORTFOLIO_ANALYSIS = False  # Coming soon

# ============================================================================
# Utility Functions
# ============================================================================

def get_setup_score(setup_name: str) -> float:
    """Get base score for a setup type."""
    return SETUP_SCORES.get(setup_name, 0.10)


def get_scoring_weight(component: str) -> float:
    """Get weight for a scoring component."""
    return SCORE_WEIGHTS.get(component, 0.0)


def is_allowed_symbol(symbol: str) -> bool:
    """Check if symbol is allowed to trade."""
    return symbol not in EXCLUDED_SYMBOLS


def get_hold_period_days(horizon: str) -> int:
    """Get number of trading days for a hold period."""
    return HOLD_PERIODS.get(horizon, 1)
