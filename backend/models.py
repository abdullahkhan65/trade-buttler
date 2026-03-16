from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    signal_type = Column(String)  # forming / confirmed
    direction = Column(String)    # BUY / SELL
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    confidence = Column(Float)    # 0-100
    score = Column(Integer)       # 0-9
    reasons = Column(Text)        # JSON array as text
    status = Column(String, default="forming")  # forming/confirmed/closed/skipped
    result = Column(String, nullable=True)       # win/loss/null
    pnl_pips = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    triggered_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    price = Column(Float)
    timestamp = Column(DateTime, server_default=func.now())


class PaperTrade(Base):
    """A virtual trade executed by the autonomous paper trading engine."""
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(String, index=True)   # e.g. "1h_baseline"
    symbol = Column(String, index=True)
    timeframe = Column(String)                 # 1h / 15m / 4h
    direction = Column(String)                 # BUY / SELL
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    lot_size = Column(Float, nullable=True)    # MT5-style lots (balance/100)
    units = Column(Float)                      # position size in asset units
    risk_usd = Column(Float)                   # dollars at risk
    status = Column(String, default="open")    # open / closed
    result = Column(String, nullable=True)     # win / loss
    exit_price = Column(Float, nullable=True)
    pnl_usd = Column(Float, nullable=True)
    score = Column(Integer)
    reasons = Column(Text)                     # JSON
    analysis = Column(Text, nullable=True)     # post-trade notes
    opened_at = Column(DateTime, server_default=func.now())
    closed_at = Column(DateTime, nullable=True)


class PaperPortfolio(Base):
    """Running balance and stats for each paper trading strategy."""
    __tablename__ = "paper_portfolio"

    id = Column(Integer, primary_key=True)
    strategy_id = Column(String, unique=True, index=True)
    label = Column(String)
    timeframe = Column(String)
    balance = Column(Float, default=500.0)
    initial_balance = Column(Float, default=500.0)
    peak_balance = Column(Float, default=500.0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now())
    # Daily session tracking
    day_start_balance = Column(Float, nullable=True)   # balance at start of today
    last_day_reset = Column(String, nullable=True)     # YYYY-MM-DD
    daily_profit_target_pct = Column(Float, default=2.0)   # stop new trades at +2%/day
    daily_risk_limit_pct = Column(Float, default=10.0)     # stop new trades at -10%/day


class DailyAnalysisReport(Base):
    """Auto-generated trade analysis report — produced every 6 hours."""
    __tablename__ = "daily_analysis_reports"

    id = Column(Integer, primary_key=True)
    report_date = Column(String)        # YYYY-MM-DD HH:MM
    total_trades = Column(Integer)
    insights = Column(Text)             # JSON list of insight strings
    recommendations = Column(Text)      # JSON list of recommendation strings
    strategy_data = Column(Text)        # JSON dict — per-strategy performance
    factor_data = Column(Text)          # JSON dict — per-factor win rates
    created_at = Column(DateTime, server_default=func.now())
