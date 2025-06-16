# trading_bot_backend/main.py
from fastapi import FastAPI, Depends, HTTPException, status, Path as FastApiPath, WebSocket, WebSocketDisconnect
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging
import asyncio # Required for asyncio.Lock, asyncio.to_thread
import time # For heartbeat timestamp if used

# Assuming bot_logic and auth are in the correct package structure
from trading_bot_backend.bot.bot_logic import BasicBot
from trading_bot_backend.auth import get_current_username
from binance.exceptions import BinanceAPIException # To catch specific exceptions in run_sync_bot_method

logger = logging.getLogger("api") # Consistent logger name for the API module
# Centralized logging config. Ensure this is the single point of basicConfig.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S" # Added date format
)

app = FastAPI(title="Trading Bot API", version="0.1.0")

# --- Pydantic Models ---
class OrderRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    side: str = Field(..., example="BUY")
    quantity: float = Field(..., gt=0)

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
    class Config: allow_population_by_field_name = True

class GridRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    lower_price: float = Field(..., alias="lowerPrice", gt=0)
    upper_price: float = Field(..., alias="upperPrice", gt=0)
    grids: int = Field(..., gt=1)
    quantity_per_grid: float = Field(..., alias="quantityPerGrid", gt=0)
    side: str = Field(..., example="BUY")
    class Config: allow_population_by_field_name = True

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
    return bot_singleton

# --- FastAPI Event Handlers ---
@app.on_event("startup")
async def startup_event_handler():
    logger.info("FastAPI application startup process initiated.")
    try:
        await get_bot_singleton() # This will initialize the bot
        logger.info("FastAPI startup complete. BasicBot singleton has been initialized.")
    except HTTPException as e:
        logger.critical(f"FastAPI startup failed due to bot initialization error: {e.detail}", exc_info=True)
        # Consider if app should exit if bot fails to init. For now, it logs.
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
async def websocket_updates_endpoint(websocket: WebSocket, bot: BasicBot = Depends(get_bot_singleton)):
    await websocket.accept()
    logger.info(f"WebSocket client connected: {websocket.client}")
    await bot.add_websocket_client(websocket)

    try:
        while True:
            # Keep the connection alive. FastAPI's WebSocket handles PING/PONG.
            # If client sends a message, it would be received here:
            # data = await websocket.receive_text()
            # logger.debug(f"WS received from {websocket.client}: {data}")
            await asyncio.sleep(60) # Example: check connection state or send heartbeat less frequently
            # Optional: send a custom heartbeat if needed for specific client/proxy requirements
            # await websocket.send_json({"type": "heartbeat", "timestamp": time.time()})

    except WebSocketDisconnect:
        logger.info(f"WebSocket client {websocket.client} disconnected (WebSocketDisconnect).")
    except Exception as e:
        logger.error(f"Error in WebSocket connection for {websocket.client}: {e}", exc_info=True)
    finally:
        logger.info(f"Cleaning up WebSocket client {websocket.client} from active list.")
        await bot.remove_websocket_client(websocket)

# --- Helper for Sync Bot Methods ---
async def run_sync_bot_method(bot_method, *args, **kwargs):
    try:
        return await asyncio.to_thread(bot_method, *args, **kwargs)
    except BinanceAPIException as e:
        logger.error(f"Binance API Error in {bot_method.__name__}: {e.message} (Code: {e.code})", exc_info=True)
        status_code = status.HTTP_400_BAD_REQUEST # Default for API errors that are often client-input related
        # More specific error codes from Binance that indicate server-side issues could be 500/502/503.
        # Example: -1001 (INTERNAL_ERROR), -1002 (SERVICE_UNAVAILABLE), -1003 (UNKNOWN_ERROR)
        if e.code in [-1001, -1002, -1003]: # Example codes for server issues
            status_code = status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=f"Binance API Error ({e.code}): {e.message}")
    except ValueError as e:
        logger.warning(f"Validation Error in {bot_method.__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Validation Error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in {bot_method.__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Server error: {str(e)}")

# --- HTTP Endpoints ---
@app.get("/")
async def read_root(): return {"message": "Welcome to the Trading Bot API"}

@app.get("/users/me", summary="Get current authenticated user", tags=["Users"])
async def read_current_user(username: str = Depends(get_current_username)): return {"username": username}

@app.get("/bot/verify-access", response_model=BotResponse, summary="Verify API access", tags=["Bot Control"])
async def verify_bot_access(username: str = Depends(get_current_username), bot: BasicBot = Depends(get_bot_singleton)):
    result = await run_sync_bot_method(bot.verify_spot_access)
    return BotResponse(**result)

@app.get("/account/balance", response_model=BotResponse, summary="Get account balances", tags=["Account"])
async def get_account_balance(username: str = Depends(get_current_username), bot: BasicBot = Depends(get_bot_singleton)):
    result = await run_sync_bot_method(bot.get_account_info)
    return BotResponse(**result)

@app.get("/symbols/{symbol_name}", response_model=SymbolInfoResponse, summary="Get symbol information", tags=["Market Data"])
async def get_symbol_information(
    symbol_name: str = FastApiPath(..., example="BTCUSDT"), username: str = Depends(get_current_username), bot: BasicBot = Depends(get_bot_singleton)):
    result = await run_sync_bot_method(bot.get_symbol_info, symbol=symbol_name.upper())
    return SymbolInfoResponse(**result)

@app.post("/orders/market", response_model=BotResponse, summary="Place a market order", tags=["Trading"])
async def place_market_order(order_req: OrderRequest, username: str = Depends(get_current_username), bot: BasicBot = Depends(get_bot_singleton)):
    # Assuming bot.place_order returns a dict like {"status": "success", "order": order_details}
    result = await run_sync_bot_method(bot.place_order, symbol=order_req.symbol, side=order_req.side, order_type="MARKET", quantity=order_req.quantity)
    return BotResponse(**result)

@app.post("/orders/limit", response_model=BotResponse, summary="Place a limit order", tags=["Trading"])
async def place_limit_order(order_req: LimitOrderRequest, username: str = Depends(get_current_username), bot: BasicBot = Depends(get_bot_singleton)):
    result = await run_sync_bot_method(bot.place_order, symbol=order_req.symbol, side=order_req.side, order_type="LIMIT", quantity=order_req.quantity, price=order_req.price)
    return BotResponse(**result)

@app.post("/orders/stop-market", response_model=BotResponse, summary="Place a stop-market order", tags=["Trading"])
async def place_stop_market_order(order_req: StopMarketOrderRequest, username: str = Depends(get_current_username), bot: BasicBot = Depends(get_bot_singleton)):
    result = await run_sync_bot_method(bot.place_order, symbol=order_req.symbol, side=order_req.side, order_type="STOP_MARKET", quantity=order_req.quantity, stop_price=order_req.stop_price)
    return BotResponse(**result)

@app.post("/strategies/twap", response_model=BotResponse, summary="Initiate a TWAP strategy", tags=["Strategies"])
async def run_twap_strategy(req: TwapRequest, username: str = Depends(get_current_username), bot: BasicBot = Depends(get_bot_singleton)):
    # Assuming bot.twap returns a dict like {"status": "success", "message": "...", "orders_placed": []}
    result = await run_sync_bot_method(bot.twap, symbol=req.symbol, side=req.side, total_qty=req.total_quantity, interval_sec=req.interval_seconds, slices=req.slices)
    return BotResponse(**result)

@app.post("/strategies/grid", response_model=BotResponse, summary="Initiate a Grid trading strategy", tags=["Strategies"])
async def run_grid_strategy(req: GridRequest, username: str = Depends(get_current_username), bot: BasicBot = Depends(get_bot_singleton)):
    result = await run_sync_bot_method(bot.grid, symbol=req.symbol, lower_price=req.lower_price, upper_price=req.upper_price, grids=req.grids, quantity=req.quantity_per_grid, side=req.side)
    return BotResponse(**result)

```
