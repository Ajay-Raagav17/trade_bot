# trading_bot_backend/main.py
from fastapi import FastAPI, Depends, HTTPException, status, Path as FastApiPath, WebSocket, WebSocketDisconnect, Query # Added Query
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict # Added ConfigDict
import logging
import asyncio
import uuid # Added
from datetime import datetime # Added
from decimal import Decimal # Added
from sqlalchemy.orm import Session # Added

# Assuming bot_logic and auth are in the correct package structure
from trading_bot_backend.bot.bot_logic import BasicBot
from trading_bot_backend.auth import get_current_user_id
from trading_bot_backend.database import get_db # Added
from trading_bot_backend.services import trade_service # Added
try:
    from trading_bot_backend.services import user_api_key_service # For upcoming UserAPIKeys CRUD
except ImportError:
    user_api_key_service = None
    logging.getLogger("api").warning("user_api_key_service not found. Critical features will fail.")

from trading_bot_backend.schemas.trade_schemas import Trade as TradeResponseSchema, PaginatedTradeHistoryResponse # Added
from binance.client import Client # Added for type hinting in get_user_bot
from binance.exceptions import BinanceAPIException

logger = logging.getLogger("api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

app = FastAPI(title="Trading Bot API", version="0.1.3") # Incremented version

# --- Pydantic Models ---
class OrderRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    side: str = Field(..., example="BUY")
    quantity: float = Field(..., gt=0)
    client_order_id: Optional[str] = Field(None, min_length=1, max_length=36, description="Optional custom order ID")
    model_config = ConfigDict(populate_by_name=False, arbitrary_types_allowed=True)

class LimitOrderRequest(OrderRequest):
    price: float = Field(..., gt=0)

class StopMarketOrderRequest(OrderRequest):
    stop_price: float = Field(..., gt=0)

class TwapRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    side: str = Field(..., example="BUY")
    total_quantity: float = Field(..., alias="totalQuantity", gt=0)
    slices: int = Field(..., gt=0)
    interval_seconds: int = Field(..., alias="intervalSeconds", gt=0)
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class GridRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    lower_price: float = Field(..., alias="lowerPrice", gt=0)
    upper_price: float = Field(..., alias="upperPrice", gt=0)
    grids: int = Field(..., gt=1)
    quantity_per_grid: float = Field(..., alias="quantityPerGrid", gt=0)
    side: str = Field(..., example="BUY")
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class BotResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    order: Optional[Dict[str, Any]] = None
    orders_placed: Optional[List[Dict[str, Any]]] = None
    balances: Optional[List[Dict[str, Any]]] = None

class SymbolInfoResponse(BaseModel):
    status: str = "success"
    data: Dict[str, Any]

# --- Bot Instance Management (Singleton Pattern) ---
bot_singleton: Optional[BasicBot] = None
bot_init_lock = asyncio.Lock()

async def get_bot_singleton() -> BasicBot:
    global bot_singleton
    if bot_singleton is None:
        async with bot_init_lock:
            if bot_singleton is None:
                logger.info("Initializing BasicBot singleton instance...")
                try:
                    bot_singleton = BasicBot()
                except Exception as e:
                    logger.critical(f"CRITICAL: BasicBot singleton initialization failed: {e}", exc_info=True)
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                        detail=f"Core trading component failed to initialize: {str(e)}")
    if bot_singleton is None:
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                             detail="Core trading component not available after initialization attempt.")
    if bot_singleton is None:
         raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                             detail="Core trading component not available after initialization attempt.")
    return bot_singleton

# --- FastAPI Event Handlers ---
@app.on_event("startup")
async def startup_event_handler():
    logger.info("FastAPI application startup process initiated.")
    try:
        await get_bot_singleton()
        logger.info("FastAPI startup complete. BasicBot singleton has been initialized.")
    except HTTPException as e:
        logger.critical(f"FastAPI startup failed due to bot initialization error: {e.detail}", exc_info=True)
    except Exception as e:
        logger.critical(f"Unexpected error during FastAPI startup's bot initialization: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event_handler():
    logger.info("FastAPI application shutting down...")
    if bot_singleton is not None and hasattr(bot_singleton, 'user_data_stream_started') and bot_singleton.user_data_stream_started:
        logger.info("Attempting to stop user data stream before shutdown...")
        try:
            await bot_singleton.stop_user_data_stream()
            logger.info("User data stream stopped successfully.")
        except Exception as e:
            logger.error(f"Error stopping user data stream during shutdown: {e}", exc_info=True)
    else:
        logger.info("User data stream was not active or bot not initialized/available; no stream to stop.")
    logger.info("FastAPI shutdown process complete.")

# --- WebSocket Endpoint ---
@app.websocket("/ws/updates")
async def websocket_endpoint( # Renamed function
    ws: WebSocket, # Renamed from websocket to ws for brevity
    token: str = Query(...), # Changed: token is now mandatory query parameter
    bot: BasicBot = Depends(get_bot_singleton),
    db: Session = Depends(get_db)
):
    user_uuid: Optional[uuid.UUID] = None; key_db_id: Optional[int] = None
    try:
        user_id_str = await get_current_user_id(token=token) # Validate token from query
        user_uuid = uuid.UUID(user_id_str)
        if not user_api_key_service: # Check if the service was imported
            logger.error(f"WS User {user_uuid}: UserAPIKeyService not available. Cannot start user stream.")
            await ws.close(status.WS_1011_INTERNAL_ERROR, "Key service unavailable.")
            return

        key_rec = await asyncio.to_thread(user_api_key_service.get_active_valid_api_key_for_user, db=db, user_id=user_uuid)
        if not key_rec:
            logger.warning(f"WS User {user_uuid}: No active/valid API key in DB.")
            await ws.close(status.WS_1008_POLICY_VIOLATION, "No active/valid API key."); return
        key_db_id = key_rec.id
        api_key = await asyncio.to_thread(user_api_key_service.get_decrypted_api_key, db_key=key_rec)
        api_secret = await asyncio.to_thread(user_api_key_service.get_decrypted_api_secret, db_key=key_rec)
        if not api_key or not api_secret:
            logger.error(f"WS User {user_uuid}: Key ID {key_db_id} decryption failed.")
            await ws.close(status.WS_1008_POLICY_VIOLATION, "API key processing error."); return

        await ws.accept()
        logger.info(f"WS client accepted for user {user_uuid} (KeyID: {key_db_id})")
        # Start user-specific data stream using their decrypted keys
        await bot.start_user_data_stream(
            user_id=user_uuid, user_api_key_id=key_db_id, # Pass DB ID of the key
            api_key=api_key, api_secret=api_secret
        )
        await bot.add_websocket_client(ws) # Add to broadcast list

        while True: await asyncio.sleep(3600) # Keep connection alive
    except WebSocketDisconnect:
        logger.info(f"WS client disconnected: User {user_uuid}, KeyID {key_db_id}")
    except HTTPException as e: # Catch auth errors from get_current_user_id or others
        logger.warning(f"WS Auth or setup failed (HTTPException): {e.detail}")
        await ws.close(status.WS_1008_POLICY_VIOLATION, f"Auth/setup error: {e.detail}")
    except Exception as e: # Catch other unexpected errors
        logger.error(f"WS error for User {user_uuid}: {e}", exc_info=True)
        # Try to close gracefully if not already closed
        if not ws.client_state == ws.client_state.DISCONNECTED:
            await ws.close(status.WS_1011_INTERNAL_ERROR, "Server error during WS session")
    finally:
        logger.info(f"WS client cleanup for User {user_uuid}")
        await bot.remove_websocket_client(ws) # This handles stopping stream if last client


# --- Helper for User-Specific Bot Operations (HTTP Requests) ---
async def get_user_bot(user_id: uuid.UUID, db: Session) -> BasicBot:
    """
    Creates a TEMPORARY BasicBot instance configured with the user's active API key.
    This is for use in HTTP requests that require user-specific Binance API interaction.
    """
    if not user_api_key_service:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")

    active_key_record = await asyncio.to_thread(user_api_key_service.get_active_valid_api_key_for_user, db=db, user_id=user_id)
    if not active_key_record:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No active/valid API key for user to perform this action.")

    decrypted_key = await asyncio.to_thread(user_api_key_service.get_decrypted_api_key, db_key=active_key_record)
    decrypted_secret = await asyncio.to_thread(user_api_key_service.get_decrypted_api_secret, db_key=active_key_record)

    if not decrypted_key or not decrypted_secret:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "API key decryption failed for user.")

    # Return a new BasicBot instance configured with these specific keys for this request
    return BasicBot(api_key=decrypted_key, api_secret=decrypted_secret)

async def run_on_user_bot_wrapper(user_id: uuid.UUID, db: Session, method_name: str, *args, **kwargs) -> Any:
    """
    Wrapper to get a user-specific bot instance and run one of its synchronous methods in a thread.
    Handles common exceptions.
    """
    user_bot = await get_user_bot(user_id, db)
    method_to_call = getattr(user_bot, method_name)

    try:
        return await asyncio.to_thread(method_to_call, *args, **kwargs)
    except BinanceAPIException as e:
        logger.error(f"User {user_id} - Binance API Error in {method_name}: {e.code} - {e.message}", exc_info=True)
        # More nuanced error codes for Binance could be mapped here
        status_code = status.HTTP_400_BAD_REQUEST if e.code < -2000 and e.code != -1021 else status.HTTP_502_BAD_GATEWAY # -1021: Timestamp issue
        raise HTTPException(status_code=status_code, detail=f"Binance API Error ({e.code}): {e.message}")
    except ValueError as e: # For validation errors within bot methods
        logger.warning(f"User {user_id} - Validation Error in {method_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Validation Error: {str(e)}")
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"User {user_id} - Unexpected error in {method_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Server error: {str(e)}")


# --- HTTP Endpoints ---
@app.get("/")
async def root(): return {"message": "Trading Bot API"} # Renamed function

@app.get("/users/me", summary="Get current authenticated user ID", tags=["Users"])
async def users_me(current_user_id: str = Depends(get_current_user_id)):
    return {"user_id": current_user_id, "message": "Authenticated."}

@app.get("/bot/verify-access", response_model=BotResponse, summary="Verify API access with user's active key", tags=["Bot Control"])
async def verify_access_endpoint(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)): # Renamed
    return await run_on_user_bot_wrapper(uuid.UUID(current_user_id), db, "verify_spot_access")

@app.get("/account/balance", response_model=BotResponse, summary="Get account balances with user's active key", tags=["Account"])
async def account_balance_endpoint(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)): # Renamed
    return await run_on_user_bot_wrapper(uuid.UUID(current_user_id), db, "get_account_info")

@app.get("/symbols/{symbol_name}", response_model=SymbolInfoResponse, summary="Get symbol information (uses global key)", tags=["Market Data"])
async def symbol_info_endpoint( # Renamed
    symbol_name: str = FastApiPath(...,example="BTCUSDT"),
    current_user_id: str = Depends(get_current_user_id), # Auth still required
    bot: BasicBot = Depends(get_bot_singleton) # Uses global bot instance for general info
):
    try:
        result = await asyncio.to_thread(bot.get_symbol_info, symbol=symbol_name.upper())
        return SymbolInfoResponse(**result)
    except ValueError as e: raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except Exception as e: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@app.post("/orders/{order_action}", response_model=BotResponse, summary="Place an order (uses user's active key)", tags=["Trading"])
async def post_order_endpoint( # Renamed and consolidated
    order_action: str,
    order_data: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user_id)
    parsed_req: Any; otype_for_bot: str
    try:
        if order_action == "market": parsed_req = OrderRequest(**order_data); otype_for_bot = "MARKET"
        elif order_action == "limit": parsed_req = LimitOrderRequest(**order_data); otype_for_bot = "LIMIT"
        elif order_action == "stop-market": parsed_req = StopMarketOrderRequest(**order_data); otype_for_bot = "STOP_MARKET" # Mapped in bot_logic
        else: raise HTTPException(400, f"Invalid order action: {order_action}. Supported: market, limit, stop-market.")
    except Exception as e_pydantic:
        logger.error(f"Pydantic validation error for /orders/{order_action}: {e_pydantic}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid order data: {str(e_pydantic)}")

    return await run_on_user_bot_wrapper(user_uuid, db, "place_order",
        symbol=parsed_req.symbol, side=parsed_req.side, order_type=otype_for_bot,
        quantity=parsed_req.quantity, price=getattr(parsed_req,'price',None),
        stop_price=getattr(parsed_req,'stop_price',None), client_order_id=getattr(parsed_req,'client_order_id',None))

@app.post("/strategies/{strategy_type}", response_model=BotResponse, summary="Initiate a strategy (uses user's active key)", tags=["Strategies"])
async def post_strategy_endpoint( # Renamed and consolidated
    strategy_type: str,
    req_data: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user_id)
    parsed_req: Any; method_name: str
    try:
        if strategy_type == "twap": parsed_req = TwapRequest(**req_data); method_name = "twap"
        elif strategy_type == "grid": parsed_req = GridRequest(**req_data); method_name = "grid"
        else: raise HTTPException(400, f"Invalid strategy type: {strategy_type}")
    except Exception as e_pydantic:
        logger.error(f"Pydantic validation error for /strategies/{strategy_type}: {e_pydantic}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid strategy data: {str(e_pydantic)}")

    if strategy_type == "twap":
        return await run_on_user_bot_wrapper(user_uuid, db, method_name,
            symbol=parsed_req.symbol, side=parsed_req.side, total_qty=parsed_req.total_quantity,
            interval_sec=parsed_req.interval_seconds, slices=parsed_req.slices)
    elif strategy_type == "grid":
        return await run_on_user_bot_wrapper(user_uuid, db, method_name,
            symbol=parsed_req.symbol, lower_price=parsed_req.lower_price, upper_price=parsed_req.upper_price,
            grids=parsed_req.grids, quantity=parsed_req.quantity_per_grid, side=parsed_req.side)

    raise HTTPException(400, f"Strategy type handler not implemented: {strategy_type}")


# --- User API Keys CRUD Endpoints ---
@app.post("/users/api-keys", response_model=api_key_schemas.UserAPIKeyResponse, status_code=status.HTTP_201_CREATED, tags=["User API Keys"])
async def add_user_api_key(key_data: api_key_schemas.UserAPIKeyCreate, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    try:
        db_api_key = await asyncio.to_thread(user_api_key_service.create_user_api_key, db=db, user_id=user_uuid, key_data=key_data)
        # Decrypt temporarily for preview generation only if service doesn't provide preview directly
        raw_api_key = await asyncio.to_thread(decrypt_value, db_api_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(raw_api_key)
        return api_key_schemas.UserAPIKeyResponse(
            id=db_api_key.id, user_id=db_api_key.user_id, label=db_api_key.label, is_active=db_api_key.is_active,
            binance_api_key_preview=preview, is_valid_on_binance=db_api_key.is_valid_on_binance,
            last_validated_at=db_api_key.last_validated_at, created_at=db_api_key.created_at, updated_at=db_api_key.updated_at
        )
    except ValueError as e: raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e: logger.error(f"Add API key error User {user_uuid}: {e}", exc_info=True); raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to add API key.")

@app.get("/users/api-keys", response_model=PyList[api_key_schemas.UserAPIKeyResponse], tags=["User API Keys"])
async def read_user_api_keys(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    db_keys = await asyncio.to_thread(user_api_key_service.get_user_api_keys, db=db, user_id=user_uuid)
    response_keys = []
    for db_key in db_keys:
        try:
            api_key_raw = await asyncio.to_thread(decrypt_value, db_key.binance_api_key_encrypted)
            preview = user_api_key_service.get_api_key_preview(api_key_raw)
        except Exception: preview = "Error generating preview" # Decryption might fail if key is bad
        response_keys.append(api_key_schemas.UserAPIKeyResponse(
            id=db_key.id, user_id=db_key.user_id, label=db_key.label, is_active=db_key.is_active,
            binance_api_key_preview=preview, is_valid_on_binance=db_key.is_valid_on_binance,
            last_validated_at=db_key.last_validated_at, created_at=db_key.created_at, updated_at=db_key.updated_at
        ))
    return response_keys

@app.put("/users/api-keys/{key_id}", response_model=api_key_schemas.UserAPIKeyResponse, tags=["User API Keys"])
async def update_user_api_key_endpoint(key_id: int, key_update_data: api_key_schemas.UserAPIKeyUpdate, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    updated_key = await asyncio.to_thread(user_api_key_service.update_user_api_key, db=db, user_id=user_uuid, key_id=key_id, key_update_data=key_update_data)
    if not updated_key: raise HTTPException(status.HTTP_404_NOT_FOUND, "API Key not found or not owned by user.")
    try:
        api_key_raw = await asyncio.to_thread(decrypt_value, updated_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(api_key_raw)
    except Exception: preview = "Error generating preview"
    return api_key_schemas.UserAPIKeyResponse(
        id=updated_key.id, user_id=updated_key.user_id, label=updated_key.label, is_active=updated_key.is_active,
        binance_api_key_preview=preview, is_valid_on_binance=updated_key.is_valid_on_binance,
        last_validated_at=updated_key.last_validated_at, created_at=updated_key.created_at, updated_at=updated_key.updated_at
    )

@app.delete("/users/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["User API Keys"])
async def delete_user_api_key_endpoint(key_id: int, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    success = await asyncio.to_thread(user_api_key_service.delete_user_api_key, db=db, user_id=user_uuid, key_id=key_id)
    if not success: raise HTTPException(status.HTTP_404_NOT_FOUND, "API Key not found or not owned by user.")
    return Response(status_code=status.HTTP_204_NO_CONTENT) # Ensure Response is imported from fastapi

@app.post("/users/api-keys/{key_id}/validate", response_model=api_key_schemas.UserAPIKeyResponse, tags=["User API Keys"])
async def validate_user_api_key_endpoint(key_id: int, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    try:
        await asyncio.to_thread(user_api_key_service.test_and_update_api_key_status, db=db, user_id=user_uuid, key_id=key_id)
    except ValueError as ve: raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e_test: logger.error(f"Error validating API key {key_id} for user {user_uuid}: {e_test}", exc_info=True); raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error validating API key: {e_test}")

    db_key = await asyncio.to_thread(user_api_key_service.get_user_api_key_by_id, db=db, user_id=user_uuid, key_id=key_id)
    if not db_key: raise HTTPException(status.HTTP_404_NOT_FOUND, "API Key not found after validation.")
    try:
        api_key_raw = await asyncio.to_thread(decrypt_value, db_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(api_key_raw)
    except Exception: preview = "Error generating preview"
    return api_key_schemas.UserAPIKeyResponse(
        id=db_key.id, user_id=db_key.user_id, label=db_key.label, is_active=db_key.is_active,
        binance_api_key_preview=preview, is_valid_on_binance=db_key.is_valid_on_binance,
        last_validated_at=db_key.last_validated_at, created_at=db_key.created_at, updated_at=db_key.updated_at
    )

# --- New Trade History Endpoint ---
@app.get("/trades", response_model=PaginatedTradeHistoryResponse, summary="Get user's trade history", tags=["Trading History"])
async def get_trades_endpoint(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Records per page (max 100)"),
    symbol: Optional[str]=Query(None,max_length=20, description="Filter by trading symbol (e.g., BTCUSDT)"),
    start_time: Optional[datetime]=Query(None, description="Filter by start time (ISO 8601 format)"),
    end_time: Optional[datetime]=Query(None, description="Filter by end time (ISO 8601 format)"),
    side: Optional[str]=Query(None,max_length=4, description="Filter by order side (BUY or SELL)"),
    order_type: Optional[str]=Query(None,max_length=20, description="Filter by order type (e.g., LIMIT, MARKET)"),
    status: Optional[str]=Query(None,max_length=20, description="Filter by order status (e.g., FILLED)"),
    search_term: Optional[str]=Query(None,description="Search in Binance Order ID, Client Order ID, or notes", max_length=50)
):
    try: user_uuid = uuid.UUID(current_user_id)
    except ValueError:
        logger.warning(f"Invalid user ID format from token: {current_user_id}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid user ID format.")

    skip = (page - 1) * size

    total, trades_db = await asyncio.to_thread(
        trade_service.get_trades_for_user,
        db=db, user_id=user_uuid, skip=skip, limit=size,
        symbol=symbol, start_time=start_time, end_time=end_time,
        side=side, order_type=order_type, status=status, search_term=search_term
    )

    total_pages = (total + size - 1) // size if size > 0 else 0

    validated_trades = [TradeResponseSchema.model_validate(trade) for trade in trades_db]

    return PaginatedTradeHistoryResponse(
        total=total,
        trades=validated_trades,
        page=page,
        size=len(validated_trades),
        pages=total_pages
    )

@app.get("/bot/verify-access", response_model=BotResponse, summary="Verify API access with user's active key", tags=["Bot Control"])
async def verify_access_endpoint(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)): # Renamed
    return await run_on_user_bot_wrapper(uuid.UUID(current_user_id), db, "verify_spot_access")

@app.get("/account/balance", response_model=BotResponse, summary="Get account balances with user's active key", tags=["Account"])
async def account_balance_endpoint(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)): # Renamed
    return await run_on_user_bot_wrapper(uuid.UUID(current_user_id), db, "get_account_info")

@app.get("/symbols/{symbol_name}", response_model=SymbolInfoResponse, summary="Get symbol information (uses global key)", tags=["Market Data"])
async def symbol_info_endpoint( # Renamed
    symbol_name: str = FastApiPath(...,example="BTCUSDT"),
    current_user_id: str = Depends(get_current_user_id), # Auth still required
    bot: BasicBot = Depends(get_bot_singleton) # Uses global bot instance for general info
):
    try:
        result = await asyncio.to_thread(bot.get_symbol_info, symbol=symbol_name.upper())
        return SymbolInfoResponse(**result)
    except ValueError as e: raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except Exception as e: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@app.post("/orders/{order_action}", response_model=BotResponse, summary="Place an order (uses user's active key)", tags=["Trading"])
async def post_order_endpoint( # Renamed and consolidated
    order_action: str,
    order_data: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user_id)
    parsed_req: Any; otype_for_bot: str
    try:
        if order_action == "market": parsed_req = OrderRequest(**order_data); otype_for_bot = "MARKET"
        elif order_action == "limit": parsed_req = LimitOrderRequest(**order_data); otype_for_bot = "LIMIT"
        elif order_action == "stop-market": parsed_req = StopMarketOrderRequest(**order_data); otype_for_bot = "STOP_MARKET" # Mapped in bot_logic
        else: raise HTTPException(400, f"Invalid order action: {order_action}. Supported: market, limit, stop-market.")
    except Exception as e_pydantic:
        logger.error(f"Pydantic validation error for /orders/{order_action}: {e_pydantic}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid order data: {str(e_pydantic)}")

    return await run_on_user_bot_wrapper(user_uuid, db, "place_order",
        symbol=parsed_req.symbol, side=parsed_req.side, order_type=otype_for_bot,
        quantity=parsed_req.quantity, price=getattr(parsed_req,'price',None),
        stop_price=getattr(parsed_req,'stop_price',None), client_order_id=getattr(parsed_req,'client_order_id',None))

@app.post("/strategies/{strategy_type}", response_model=BotResponse, summary="Initiate a strategy (uses user's active key)", tags=["Strategies"])
async def post_strategy_endpoint( # Renamed and consolidated
    strategy_type: str,
    req_data: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user_id)
    parsed_req: Any; method_name: str
    try:
        if strategy_type == "twap": parsed_req = TwapRequest(**req_data); method_name = "twap"
        elif strategy_type == "grid": parsed_req = GridRequest(**req_data); method_name = "grid"
        else: raise HTTPException(400, f"Invalid strategy type: {strategy_type}")
    except Exception as e_pydantic:
        logger.error(f"Pydantic validation error for /strategies/{strategy_type}: {e_pydantic}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid strategy data: {str(e_pydantic)}")

    if strategy_type == "twap":
        return await run_on_user_bot_wrapper(user_uuid, db, method_name,
            symbol=parsed_req.symbol, side=parsed_req.side, total_qty=parsed_req.total_quantity,
            interval_sec=parsed_req.interval_seconds, slices=parsed_req.slices)
    elif strategy_type == "grid":
        return await run_on_user_bot_wrapper(user_uuid, db, method_name,
            symbol=parsed_req.symbol, lower_price=parsed_req.lower_price, upper_price=parsed_req.upper_price,
            grids=parsed_req.grids, quantity=parsed_req.quantity_per_grid, side=parsed_req.side)

    raise HTTPException(400, f"Strategy type handler not implemented: {strategy_type}")


# --- User API Keys CRUD Endpoints ---
@app.post("/users/api-keys", response_model=api_key_schemas.UserAPIKeyResponse, status_code=status.HTTP_201_CREATED, tags=["User API Keys"])
async def add_user_api_key(key_data: api_key_schemas.UserAPIKeyCreate, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    try:
        db_api_key = await asyncio.to_thread(user_api_key_service.create_user_api_key, db=db, user_id=user_uuid, key_data=key_data)
        raw_api_key = await asyncio.to_thread(decrypt_value, db_api_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(raw_api_key)
        return api_key_schemas.UserAPIKeyResponse(
            id=db_api_key.id, user_id=db_api_key.user_id, label=db_api_key.label, is_active=db_api_key.is_active,
            binance_api_key_preview=preview, is_valid_on_binance=db_api_key.is_valid_on_binance,
            last_validated_at=db_api_key.last_validated_at, created_at=db_api_key.created_at, updated_at=db_api_key.updated_at
        )
    except ValueError as e: raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e: logger.error(f"Add API key error User {user_uuid}: {e}", exc_info=True); raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to add API key.")

@app.get("/users/api-keys", response_model=PyList[api_key_schemas.UserAPIKeyResponse], tags=["User API Keys"])
async def read_user_api_keys(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    db_keys = await asyncio.to_thread(user_api_key_service.get_user_api_keys, db=db, user_id=user_uuid)
    response_keys = []
    for db_key in db_keys:
        try:
            api_key_raw = await asyncio.to_thread(decrypt_value, db_key.binance_api_key_encrypted)
            preview = user_api_key_service.get_api_key_preview(api_key_raw)
        except Exception: preview = "Error generating preview" # Decryption might fail if key is bad
        response_keys.append(api_key_schemas.UserAPIKeyResponse(
            id=db_key.id, user_id=db_key.user_id, label=db_key.label, is_active=db_key.is_active,
            binance_api_key_preview=preview, is_valid_on_binance=db_key.is_valid_on_binance,
            last_validated_at=db_key.last_validated_at, created_at=db_key.created_at, updated_at=db_key.updated_at
        ))
    return response_keys

@app.put("/users/api-keys/{key_id}", response_model=api_key_schemas.UserAPIKeyResponse, tags=["User API Keys"])
async def update_user_api_key_endpoint(key_id: int, key_update_data: api_key_schemas.UserAPIKeyUpdate, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    updated_key = await asyncio.to_thread(user_api_key_service.update_user_api_key, db=db, user_id=user_uuid, key_id=key_id, key_update_data=key_update_data)
    if not updated_key: raise HTTPException(status.HTTP_404_NOT_FOUND, "API Key not found or not owned by user.")
    try:
        api_key_raw = await asyncio.to_thread(decrypt_value, updated_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(api_key_raw)
    except Exception: preview = "Error generating preview"
    return api_key_schemas.UserAPIKeyResponse(
        id=updated_key.id, user_id=updated_key.user_id, label=updated_key.label, is_active=updated_key.is_active,
        binance_api_key_preview=preview, is_valid_on_binance=updated_key.is_valid_on_binance,
        last_validated_at=updated_key.last_validated_at, created_at=updated_key.created_at, updated_at=updated_key.updated_at
    )

@app.delete("/users/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["User API Keys"])
async def delete_user_api_key_endpoint(key_id: int, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    success = await asyncio.to_thread(user_api_key_service.delete_user_api_key, db=db, user_id=user_uuid, key_id=key_id)
    if not success: raise HTTPException(status.HTTP_404_NOT_FOUND, "API Key not found or not owned by user.")
    return Response(status_code=status.HTTP_204_NO_CONTENT) # Ensure Response is imported from fastapi

@app.post("/users/api-keys/{key_id}/validate", response_model=api_key_schemas.UserAPIKeyResponse, tags=["User API Keys"])
async def validate_user_api_key_endpoint(key_id: int, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    if not user_api_key_service: raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "User API Key service unavailable.")
    try:
        await asyncio.to_thread(user_api_key_service.test_and_update_api_key_status, db=db, user_id=user_uuid, key_id=key_id)
    except ValueError as ve: raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e_test: logger.error(f"Error validating API key {key_id} for user {user_uuid}: {e_test}", exc_info=True); raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error validating API key: {e_test}")

    db_key = await asyncio.to_thread(user_api_key_service.get_user_api_key_by_id, db=db, user_id=user_uuid, key_id=key_id)
    if not db_key: raise HTTPException(status.HTTP_404_NOT_FOUND, "API Key not found after validation.")
    try:
        api_key_raw = await asyncio.to_thread(decrypt_value, db_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(api_key_raw)
    except Exception: preview = "Error generating preview"
    return api_key_schemas.UserAPIKeyResponse(
        id=db_key.id, user_id=db_key.user_id, label=db_key.label, is_active=db_key.is_active,
        binance_api_key_preview=preview, is_valid_on_binance=db_key.is_valid_on_binance,
        last_validated_at=db_key.last_validated_at, created_at=db_key.created_at, updated_at=db_key.updated_at
    )

# --- New Trade History Endpoint ---
@app.get("/trades", response_model=PaginatedTradeHistoryResponse, summary="Get user's trade history", tags=["Trading History"])
async def get_trades_endpoint(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Records per page (max 100)"),
    symbol: Optional[str]=Query(None,max_length=20, description="Filter by trading symbol (e.g., BTCUSDT)"),
    start_time: Optional[datetime]=Query(None, description="Filter by start time (ISO 8601 format)"),
    end_time: Optional[datetime]=Query(None, description="Filter by end time (ISO 8601 format)"),
    side: Optional[str]=Query(None,max_length=4, description="Filter by order side (BUY or SELL)"),
    order_type: Optional[str]=Query(None,max_length=20, description="Filter by order type (e.g., LIMIT, MARKET)"),
    status: Optional[str]=Query(None,max_length=20, description="Filter by order status (e.g., FILLED)"),
    search_term: Optional[str]=Query(None,description="Search in Binance Order ID, Client Order ID, or notes", max_length=50)
):
    try: user_uuid = uuid.UUID(current_user_id)
    except ValueError:
        logger.warning(f"Invalid user ID format from token: {current_user_id}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid user ID format.")

    skip = (page - 1) * size

    total, trades_db = await asyncio.to_thread(
        trade_service.get_trades_for_user,
        db=db, user_id=user_uuid, skip=skip, limit=size,
        symbol=symbol, start_time=start_time, end_time=end_time,
        side=side, order_type=order_type, status=status, search_term=search_term
    )

    total_pages = (total + size - 1) // size if size > 0 else 0

    validated_trades = [TradeResponseSchema.model_validate(trade) for trade in trades_db]

    return PaginatedTradeHistoryResponse(
        total=total,
        trades=validated_trades,
        page=page,
        size=len(validated_trades),
        pages=total_pages
    )

@app.get("/bot/verify-access", response_model=BotResponse, tags=["Bot Control"])
async def verify_access(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return await run_on_user_bot_wrapper(uuid.UUID(current_user_id), db, "verify_spot_access")

@app.get("/account/balance", response_model=BotResponse, tags=["Account"])
async def account_balance(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return await run_on_user_bot_wrapper(uuid.UUID(current_user_id), db, "get_account_info")

@app.get("/symbols/{symbol_name}", response_model=SymbolInfoResponse, tags=["Market Data"])
async def symbol_info(symbol_name: str = FastApiPath(...,example="BTCUSDT"), current_user_id: str = Depends(get_current_user_id), bot: BasicBot = Depends(get_bot_singleton)):
    # Symbol info can use a global/default key bot instance as it's public data
    try:
        # Use asyncio.to_thread for the direct call to the singleton's method
        result = await asyncio.to_thread(bot.get_symbol_info, symbol=symbol_name.upper())
        # Pydantic v2 model_validate is implicit if dict is returned and schema has from_attributes=True
        return SymbolInfoResponse(**result)
    except ValueError as e: raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except Exception as e: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@app.post("/orders/{order_action}", response_model=BotResponse, tags=["Trading"])
async def post_order(order_action: str, order_data: Dict[str, Any], current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    parsed_req: Any; otype_for_bot: str
    try:
        if order_action == "market": parsed_req = OrderRequest(**order_data); otype_for_bot = "MARKET"
        elif order_action == "limit": parsed_req = LimitOrderRequest(**order_data); otype_for_bot = "LIMIT"
        elif order_action == "stop-market": parsed_req = StopMarketOrderRequest(**order_data); otype_for_bot = "STOP_MARKET" # This will be mapped to STOP_LOSS in bot_logic
        else: raise HTTPException(400, f"Invalid order action: {order_action}. Supported: market, limit, stop-market.")
    except Exception as e_pydantic: # Catch Pydantic validation errors specifically
        logger.error(f"Pydantic validation error for /orders/{order_action}: {e_pydantic}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid order data: {e_pydantic}")

    return await run_on_user_bot_wrapper(user_uuid, db, "place_order",
        symbol=parsed_req.symbol, side=parsed_req.side, order_type=otype_for_bot,
        quantity=parsed_req.quantity, price=getattr(parsed_req,'price',None),
        stop_price=getattr(parsed_req,'stop_price',None), client_order_id=getattr(parsed_req,'client_order_id',None))

@app.post("/strategies/{strategy_type}", response_model=BotResponse, tags=["Strategies"])
async def post_strategy(strategy_type: str, req_data: Dict[str, Any], current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = uuid.UUID(current_user_id)
    parsed_req: Any; method_name: str
    try:
        if strategy_type == "twap": parsed_req = TwapRequest(**req_data); method_name = "twap"
        elif strategy_type == "grid": parsed_req = GridRequest(**req_data); method_name = "grid"
        else: raise HTTPException(400, f"Invalid strategy type: {strategy_type}")
    except Exception as e_pydantic:
        logger.error(f"Pydantic validation error for /strategies/{strategy_type}: {e_pydantic}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid strategy data: {e_pydantic}")

    # Pass validated Pydantic model fields as kwargs to the bot method
    if strategy_type == "twap": # For TwapRequest
        return await run_on_user_bot_wrapper(user_uuid, db, method_name,
            symbol=parsed_req.symbol, side=parsed_req.side, total_qty=parsed_req.total_quantity,
            interval_sec=parsed_req.interval_seconds, slices=parsed_req.slices)
    elif strategy_type == "grid": # For GridRequest
        return await run_on_user_bot_wrapper(user_uuid, db, method_name,
            symbol=parsed_req.symbol, lower_price=parsed_req.lower_price, upper_price=parsed_req.upper_price,
            grids=parsed_req.grids, quantity=parsed_req.quantity_per_grid, side=parsed_req.side)

    # This line should not be reached if validation is correct
    raise HTTPException(400, f"Strategy type handler not implemented or error in logic: {strategy_type}")


@app.get("/trades", response_model=PaginatedTradeHistoryResponse, tags=["Trading History"])
async def get_trades_endpoint(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Records per page (max 100)"), # Max 100 for this example
    symbol: Optional[str]=Query(None,max_length=20, description="Filter by trading symbol (e.g., BTCUSDT)"),
    start_time: Optional[datetime]=Query(None, description="Filter by start time (ISO 8601 format)"),
    end_time: Optional[datetime]=Query(None, description="Filter by end time (ISO 8601 format)"),
    side: Optional[str]=Query(None,max_length=4, description="Filter by order side (BUY or SELL)"),
    order_type: Optional[str]=Query(None,max_length=20, description="Filter by order type (e.g., LIMIT, MARKET)"),
    status: Optional[str]=Query(None,max_length=20, description="Filter by order status (e.g., FILLED)"),
    search_term: Optional[str]=Query(None,description="Search in Binance Order ID, Client Order ID, or notes", max_length=50)
):
    try: user_uuid = uuid.UUID(current_user_id)
    except ValueError:
        logger.warning(f"Invalid user ID format from token: {current_user_id}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid user ID format.")

    skip = (page - 1) * size

    total, trades_db = await asyncio.to_thread(
        trade_service.get_trades_for_user,
        db=db, user_id=user_uuid, skip=skip, limit=size,
        symbol=symbol, start_time=start_time, end_time=end_time,
        side=side, order_type=order_type, status=status, search_term=search_term
    )

    total_pages = (total + size - 1) // size if size > 0 else 0

    # For Pydantic v2, use model_validate. Schemas use model_config = ConfigDict(from_attributes=True)
    validated_trades = [TradeResponseSchema.model_validate(trade) for trade in trades_db]

    return PaginatedTradeHistoryResponse(
        total=total,
        trades=validated_trades,
        page=page,
        size=len(validated_trades), # Actual number of items returned on this page
        pages=total_pages
    )