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
