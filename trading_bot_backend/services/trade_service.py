from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_ # Added or_ for more flexible search
from typing import List, Optional, Tuple
from datetime import datetime
import uuid # For type hinting user_id
import logging

from trading_bot_backend.models import TradeHistory # The SQLAlchemy model
from trading_bot_backend.schemas.trade_schemas import TradeCreate # The Pydantic schema

logger = logging.getLogger(__name__)

def log_trade(db: Session, user_id: uuid.UUID, trade_data: TradeCreate) -> TradeHistory:
    """
    Logs a new trade into the database.
    user_id is the Supabase UUID.
    trade_data contains all other trade details.
    """
    logger.info(f"Logging trade for user {user_id}, symbol {trade_data.symbol}, order_id {trade_data.binance_order_id}")
    try:
        db_trade = TradeHistory(
            **trade_data.model_dump(), # Pydantic v2 .model_dump() replaces .dict()
            user_id=user_id
        )
        db.add(db_trade)
        db.commit()
        db.refresh(db_trade)
        logger.info(f"Trade logged successfully with internal ID {db_trade.id}")
        return db_trade
    except Exception as e:
        logger.error(f"Error logging trade for user {user_id}: {e}", exc_info=True)
        db.rollback() # Rollback in case of error
        raise

def get_trades_for_user(
    db: Session,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20, # Default to a smaller page size
    symbol: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    side: Optional[str] = None,
    order_type: Optional[str] = None,
    status: Optional[str] = None,
    search_term: Optional[str] = None # Generic search for order ID or notes
) -> Tuple[int, List[TradeHistory]]:
    """
    Retrieves a paginated list of trades for a specific user, with optional filters.
    """
    logger.debug(f"Fetching trades for user {user_id} with skip={skip}, limit={limit}, filters={{symbol:'{symbol}', side:'{side}' etc.}}")

    query = db.query(TradeHistory).filter(TradeHistory.user_id == user_id)

    if symbol:
        query = query.filter(TradeHistory.symbol.ilike(f"%{symbol}%"))
    if start_time:
        query = query.filter(TradeHistory.transaction_time >= start_time)
    if end_time:
        # Ensure end_time includes the whole day if only date is provided by user
        # This might require transforming end_time to end of day in the router if it's just a date
        query = query.filter(TradeHistory.transaction_time <= end_time)
    if side:
        query = query.filter(TradeHistory.side.ilike(side)) # Exact match might be better for BUY/SELL
    if order_type:
        query = query.filter(TradeHistory.order_type.ilike(f"%{order_type}%"))
    if status:
        query = query.filter(TradeHistory.status.ilike(status))

    if search_term:
        # Search in binance_order_id or notes
        search_pattern = f"%{search_term}%"
        query = query.filter(
            or_(
                TradeHistory.binance_order_id.ilike(search_pattern),
                TradeHistory.notes.ilike(search_pattern),
                TradeHistory.client_order_id.ilike(search_pattern) # Also search client_order_id
            )
        )

    # Get total count before applying limit and offset for pagination
    # Using a subquery for count for better performance on large tables with complex filters
    count_query = query.statement.with_only_columns(func.count(TradeHistory.id)).order_by(None)
    total_count = db.execute(count_query).scalar_one()

    trades = query.order_by(desc(TradeHistory.transaction_time)).offset(skip).limit(limit).all()

    logger.debug(f"Found {total_count} trades in total, returning {len(trades)} trades for this page.")
    return total_count, trades

def get_trade_by_db_id(db: Session, user_id: uuid.UUID, trade_db_id: int) -> Optional[TradeHistory]:
    """
    Retrieves a specific trade by its internal database ID, ensuring it belongs to the user.
    """
    logger.debug(f"Fetching trade by DB ID {trade_db_id} for user {user_id}")
    return db.query(TradeHistory).filter(
        TradeHistory.user_id == user_id,
        TradeHistory.id == trade_db_id
    ).first()

def get_trade_by_binance_order_id(db: Session, user_id: uuid.UUID, binance_order_id: str) -> Optional[TradeHistory]:
    """
    Retrieves a specific trade by its Binance Order ID, ensuring it belongs to the user.
    """
    logger.debug(f"Fetching trade by Binance Order ID {binance_order_id} for user {user_id}")
    return db.query(TradeHistory).filter(
        TradeHistory.user_id == user_id,
        TradeHistory.binance_order_id == binance_order_id
    ).first()

# Potential future functions:
# def update_trade_notes(db: Session, user_id: uuid.UUID, trade_db_id: int, notes: str) -> Optional[TradeHistory]: ...
# def delete_trade(db: Session, user_id: uuid.UUID, trade_db_id: int) -> bool: ...
# Note: Deleting financial records is often discouraged; consider soft delete or archiving.
```
