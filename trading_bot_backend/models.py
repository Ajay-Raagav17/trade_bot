from sqlalchemy import Column, Integer, String, Boolean, DateTime, DECIMAL, TEXT, ForeignKey, func, BigInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship

from trading_bot_backend.database import Base


class UserAPIKeys(Base):
    __tablename__ = 'user_api_keys'

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    binance_api_key_encrypted = Column(TEXT, nullable=False)
    binance_api_secret_encrypted = Column(TEXT, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_valid_on_binance = Column(Boolean, default=False, nullable=False) # Status from Binance validation
    last_validated_at = Column(DateTime(timezone=True), nullable=True) # When was it last checked with Binance
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f'<UserAPIKeys(id={self.id}, user_id={self.user_id}, label="{self.label}", is_active={self.is_active})>'


class TradeHistory(Base):
    __tablename__ = 'trade_history'

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    user_api_key_id = Column(BigInteger, ForeignKey('user_api_keys.id', ondelete='SET NULL'), nullable=True, index=True)
    # Binance Order Details
    binance_order_id = Column(String(255), nullable=False, index=True)
    client_order_id = Column(String(255), nullable=True, index=True) # Optional clientOrderId
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False) # e.g., BUY, SELL
    order_type = Column(String(50), nullable=False) # e.g., LIMIT, MARKET, STOP_LOSS_LIMIT
    status = Column(String(50), nullable=False) # e.g., FILLED, CANCELED, NEW
    time_in_force = Column(String(10), nullable=True) # e.g., GTC, IOC, FOK

    quantity_ordered = Column(DECIMAL(30, 15), nullable=False)
    quantity_filled = Column(DECIMAL(30, 15), nullable=False, default=0)
    price_ordered = Column(DECIMAL(30, 15), nullable=True) # Price for limit orders
    price_avg_filled = Column(DECIMAL(30, 15), nullable=True) # Average fill price

    commission_amount = Column(DECIMAL(30, 15), nullable=True)
    commission_asset = Column(String(20), nullable=True)

    transaction_time = Column(DateTime(timezone=True), nullable=False, index=True) # from Binance (transactTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False) # Our record creation time
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False) # Our record update time

    # Strategy & Notes
    strategy_used = Column(String(100), nullable=True, index=True)
    notes = Column(TEXT, nullable=True)

    api_key_relation = relationship('UserAPIKeys') # Renamed for clarity

    __table_args__ = (UniqueConstraint('user_id', 'binance_order_id', name='uq_user_binance_order'),)

    def __repr__(self):
        return f'<TradeHistory(id={self.id}, user_id={self.user_id}, symbol="{self.symbol}", order_id="{self.binance_order_id}")>'


class BotAuditLog(Base):
    __tablename__ = 'bot_audit_logs'

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True) # Can be null for system events
    log_level = Column(String(20), nullable=False, default='INFO', index=True)
    event_type = Column(String(100), index=True, nullable=False)
    message = Column(TEXT, nullable=False)
    details_json = Column(JSONB, nullable=True) # For structured data like request/response snippets

    def __repr__(self):
        return f'<BotAuditLog(id={self.id}, timestamp={self.timestamp}, event_type="{self.event_type}", user_id={self.user_id})>'

# Example of a simple User model if we were managing users directly (not using Supabase Auth for this table)
# class User(Base):
#     __tablename__ = 'users'
#     id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     email = Column(String, unique=True, index=True, nullable=False)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     api_keys = relationship('UserAPIKeys', back_populates='user')
