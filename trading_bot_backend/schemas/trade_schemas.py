from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List as PyList
from datetime import datetime
from decimal import Decimal
import uuid

class TradeBase(BaseModel):
    binance_order_id: str = Field(..., example="123456789012345", description="The unique order ID assigned by Binance.")
    symbol: str = Field(..., example="BTCUSDT", description="Trading symbol, e.g., BTCUSDT.")
    side: str = Field(..., example="BUY", description="Order side: BUY or SELL.")
    order_type: str = Field(..., example="LIMIT", description="Type of order, e.g., LIMIT, MARKET, STOP_LOSS_LIMIT.")
    status: str = Field(..., example="FILLED", description="Current status of the order on Binance, e.g., FILLED, CANCELED, NEW.")

    quantity_ordered: Decimal = Field(..., example=Decimal("0.001"), description="The quantity originally requested in the order.")
    quantity_filled: Decimal = Field(..., example=Decimal("0.001"), description="The total quantity of the order that has been filled.")

    price_ordered: Optional[Decimal] = Field(None, example=Decimal("50000.00"), description="The price at which a LIMIT order was placed. May be null for MARKET orders if not applicable.")
    price_avg_filled: Optional[Decimal] = Field(None, example=Decimal("50000.50"), description="The average price at which the filled quantity was executed. May be null if not applicable or not filled.")

    commission_amount: Optional[Decimal] = Field(None, example=Decimal("0.00000075"), description="Total commission paid for this trade, in the commission asset.")
    commission_asset: Optional[str] = Field(None, example="BNB", description="The asset in which commission was paid (e.g., BNB, USDT).")

    transaction_time: datetime = Field(..., description="Timestamp of the trade execution or last update from Binance (maps to `transactTime` from Binance order details).")

    strategy_used: Optional[str] = Field(None, example="TWAP_BTC_HOURLY_V1", max_length=100, description="Identifier for the trading strategy that executed this trade, if any.")
    notes: Optional[str] = Field(None, example="Part of hourly TWAP execution for BTC.", max_length=500, description="User-defined or system-generated notes related to this trade.")
    user_api_key_id: Optional[int] = Field(None, description="Internal database ID of the User's API Key record used for this trade, if this trade was made through the bot.")
    client_order_id: Optional[str] = Field(None, example="my_custom_order_id_12345", max_length=255, description="Optional client-assigned order ID that was sent to Binance.")
    time_in_force: Optional[str] = Field(None, example="GTC", max_length=10, description="Time in force for the order (e.g., GTC, IOC, FOK), if applicable.")

class TradeCreate(TradeBase):
    # user_id is not part of this schema; it's injected by the service layer
    # based on the authenticated user making the request (or system context for WebSocket logs).
    pass

class Trade(TradeBase):
    id: int = Field(..., description="Internal database ID of this trade record.")
    user_id: uuid.UUID = Field(..., description="The user ID (Supabase UUID) associated with this trade.")
    created_at: datetime = Field(..., description="Timestamp when this trade record was created in our database.")
    updated_at: datetime = Field(..., description="Timestamp when this trade record was last updated in our database.")

    model_config = ConfigDict(from_attributes=True)

class PaginatedTradeHistoryResponse(BaseModel):
    total: int = Field(..., example=125, description="Total number of trade records matching the query criteria.")
    trades: PyList[Trade] = Field(..., description="List of trade records for the current page.")
    page: int = Field(..., example=1, description="Current page number (1-indexed).")
    size: int = Field(..., example=20, description="Actual number of trades returned in this page (can be less than requested size if it's the last page).")
    pages: Optional[int] = Field(None, example=7, description="Total number of pages available based on total records and requested page size.")
```
