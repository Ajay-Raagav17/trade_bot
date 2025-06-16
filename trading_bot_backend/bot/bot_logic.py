import logging
import time
import os
import asyncio
from typing import List, Any, Dict, Optional
from decimal import Decimal
import uuid

from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from binance import ThreadedWebsocketManager

try:
    from trading_bot_backend.bot.env import API_KEY as DEFAULT_BOT_API_KEY
    from trading_bot_backend.bot.env import API_SECRET as DEFAULT_BOT_API_SECRET
except ImportError:
    DEFAULT_BOT_API_KEY = os.getenv('BINANCE_API_KEY', "your_binance_api_key_here")
    DEFAULT_BOT_API_SECRET = os.getenv('BINANCE_API_SECRET', "your_binance_api_secret_here")

from trading_bot_backend.services import trade_service
from trading_bot_backend.schemas.trade_schemas import TradeCreate
from trading_bot_backend.database import SessionLocal # type: ignore
from sqlalchemy.orm import Session # For type hinting db_session_for_log
from datetime import datetime

DEFAULT_SYMBOL = "BTCUSDT"

class BasicBot:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.logger = logging.getLogger("trading_bot_api.BasicBot")
        self.instance_api_key = api_key or DEFAULT_BOT_API_KEY
        self.instance_api_secret = api_secret or DEFAULT_BOT_API_SECRET

        is_placeholder_key = not self.instance_api_key or "your_binance_api_key_here" in self.instance_api_key
        is_placeholder_secret = not self.instance_api_secret or "your_binance_api_secret_here" in self.instance_api_secret
        if is_placeholder_key or is_placeholder_secret: # Check against actual default values from env too
             if self.instance_api_key == DEFAULT_BOT_API_KEY and "your_binance_api_key_here" not in str(DEFAULT_BOT_API_KEY): # Avoid warning if default is a real key
                 pass
             elif self.instance_api_secret == DEFAULT_BOT_API_SECRET and "your_binance_api_secret_here" not in str(DEFAULT_BOT_API_SECRET):
                 pass
             else:
                self.logger.warning("BasicBot instance using placeholder Binance API credentials.")

        try:
            self.client = Client(self.instance_api_key, self.instance_api_secret, testnet=True)
            self.logger.info(f"BasicBot instance initialized. Testnet: True. API Key: ...{self.instance_api_key[-4:] if self.instance_api_key and len(self.instance_api_key) >= 4 else 'N/A'}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Binance Client: {e}", exc_info=True)
            raise ValueError(f"Binance Client initialization failed: {e}")

        self.twm: Optional[ThreadedWebsocketManager] = None
        self.user_data_stream_key: Optional[str] = None
        self.active_websockets: List[Any] = []
        self.user_data_stream_started: bool = False
        self._lock = asyncio.Lock()

        self.stream_user_id: Optional[uuid.UUID] = None
        self.stream_user_api_key_id: Optional[int] = None
        self.stream_user_binance_api_key_ref: Optional[str] = None

    def verify_spot_access(self):
        try:
            account_info = self.client.get_account()
            if account_info.get('canTrade'): return {"status": "success", "message": "Spot trading access verified."}
            else: raise Exception("Spot trading not enabled for this account.")
        except BinanceAPIException as e: raise Exception(f"API Error ({e.code}): {e.message}")
        except Exception as e: raise Exception(f"Unexpected error: {str(e)}")

    def get_account_info(self):
        try:
            account_info = self.client.get_account()
            balances = [{'asset': b['asset'], 'free': str(b['free']), 'locked': str(b['locked'])}
                                 for b in account_info['balances'] if float(b['free']) > 0 or float(b['locked']) > 0]
            return {"status": "success", "balances": balances}
        except BinanceAPIException as e: raise Exception(f"API Error ({e.code}): {e.message}")
        except Exception as e: raise Exception(f"Unexpected error: {str(e)}")

    def get_symbol_info(self, symbol: str):
        try:
            info = self.client.get_symbol_info(symbol)
            if not info: raise ValueError(f"Symbol {symbol} not found")
            return {"status": "success", "data": info}
        except BinanceAPIException as e: raise Exception(f"API Error ({e.code}): {e.message}")
        except Exception as e: raise Exception(f"Unexpected error: {str(e)}")

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None, stop_price: Optional[float] = None, client_order_id: Optional[str] = None):
        try:
            self.client.get_symbol_info(symbol)
            params: Dict[str, Any] = {'symbol': symbol.upper(), 'side': side.upper(), 'quantity': quantity}
            if client_order_id: params['newClientOrderId'] = client_order_id

            order_type_upper = order_type.upper()
            # Ensure Binance ENUMs are used where appropriate for 'type'
            if order_type_upper == "MARKET": params['type'] = ORDER_TYPE_MARKET
            elif order_type_upper == "LIMIT": params['type'] = ORDER_TYPE_LIMIT
            elif order_type_upper == "STOP_LOSS": params['type'] = ORDER_TYPE_STOP_LOSS
            elif order_type_upper == "STOP_LOSS_LIMIT": params['type'] = ORDER_TYPE_STOP_LOSS_LIMIT
            elif order_type_upper == "TAKE_PROFIT": params['type'] = ORDER_TYPE_TAKE_PROFIT
            elif order_type_upper == "TAKE_PROFIT_LIMIT": params['type'] = ORDER_TYPE_TAKE_PROFIT_LIMIT
            elif order_type_upper == "LIMIT_MAKER": params['type'] = ORDER_TYPE_LIMIT_MAKER
            elif order_type_upper == "STOP_MARKET": params['type'] = ORDER_TYPE_STOP_LOSS # Custom mapping
            else: raise ValueError(f"Unsupported order_type: {order_type}")

            if order_type_upper in [ORDER_TYPE_LIMIT, ORDER_TYPE_STOP_LOSS_LIMIT, ORDER_TYPE_TAKE_PROFIT_LIMIT, ORDER_TYPE_LIMIT_MAKER]:
                if price is None: raise ValueError(f"Price required for {order_type_upper}")
                params['price'] = self.client.format_price(symbol=symbol, price=str(price))
            if order_type_upper in [ORDER_TYPE_LIMIT, ORDER_TYPE_STOP_LOSS_LIMIT, ORDER_TYPE_TAKE_PROFIT_LIMIT]:
                 params['timeInForce'] = TIME_IN_FORCE_GTC # Default for these

            if order_type_upper in [ORDER_TYPE_STOP_LOSS, ORDER_TYPE_STOP_LOSS_LIMIT, ORDER_TYPE_TAKE_PROFIT, ORDER_TYPE_TAKE_PROFIT_LIMIT, "STOP_MARKET"]:
                if stop_price is None: raise ValueError(f"Stop price required for {order_type_upper}")
                params['stopPrice'] = self.client.format_price(symbol=symbol, price=str(stop_price))

            self.logger.info(f"Placing order: {params}")
            new_order = self.client.create_order(**params)
            return {"status": "success", "order": new_order}
        except BinanceAPIException as e: self.logger.error(f"Order error: {e}"); raise Exception(f"API Error ({e.code}): {e.message}")
        except Exception as e: self.logger.error(f"Order error: {e}"); raise Exception(f"Error: {str(e)}")

    def twap(self, symbol: str, side: str, total_qty: float, interval_sec: int, slices: int):
        self.logger.info(f"TWAP: {symbol}, side {side}, total_qty {total_qty}, slices {slices}, interval {interval_sec}s")
        placed_orders_summary = []
        qty_per_order = round(total_qty / slices, 8)
        for i in range(slices):
            client_order_id = f"twap_{symbol.lower()}_{side.lower()}_{int(time.time())}_{i+1}"
            try:
                order_result = self.place_order(symbol, side, "MARKET", qty_per_order, client_order_id=client_order_id)
                placed_orders_summary.append(order_result.get("order", {}))
            except Exception as e_slice:
                self.logger.error(f"TWAP slice {i+1} failed: {e_slice}")
                placed_orders_summary.append({"error": str(e_slice), "slice": i+1, "client_order_id": client_order_id})
            if i < slices - 1: time.sleep(interval_sec)
        return {'status': 'success', 'message': 'TWAP execution attempted.', 'orders_placed': placed_orders_summary}

    def grid(self, symbol: str, lower_price: float, upper_price: float, grids: int, quantity: float, side: str):
        self.logger.info(f"Grid: {symbol}, side {side}, range {lower_price}-{upper_price}, grids {grids}, qty {quantity}")
        placed_orders_summary = []
        if grids <= 1: raise ValueError("Grids must be > 1")
        price_step = (upper_price - lower_price) / (grids - 1)
        for i in range(grids):
            price = round(lower_price + i * price_step, 8)
            client_order_id = f"grid_{symbol.lower()}_{side.lower()}_{int(time.time())}_{i+1}"
            try:
                order_result = self.place_order(symbol, side, "LIMIT", quantity, price=price, client_order_id=client_order_id)
                placed_orders_summary.append(order_result.get("order", {}))
            except Exception as e_slice:
                self.logger.error(f"Grid order {i+1} at {price} failed: {e_slice}")
                placed_orders_summary.append({"error": str(e_slice), "slice": i+1, "price":price, "client_order_id": client_order_id})
        return {'status': 'success', 'message': 'Grid setup attempted.', 'orders_placed': placed_orders_summary}

    async def add_websocket_client(self, websocket: Any):
        async with self._lock:
            if websocket not in self.active_websockets: self.active_websockets.append(websocket)
            self.logger.info(f"WS client added. Total: {len(self.active_websockets)}")

    async def remove_websocket_client(self, websocket: Any):
        async with self._lock:
            if websocket in self.active_websockets: self.active_websockets.remove(websocket)
            self.logger.info(f"WS client removed. Total: {len(self.active_websockets)}")
        if not self.active_websockets and self.user_data_stream_started:
            await self.stop_user_data_stream()

    async def broadcast_to_clients(self, message_data: Dict[str, Any]):
        if not self.active_websockets: return
        clients_to_remove = []
        for client_ws in list(self.active_websockets):
            try: await client_ws.send_json(message_data)
            except Exception as e: clients_to_remove.append(client_ws); self.logger.error(f"WS send error to {client_ws}: {e}")
        if clients_to_remove:
            async with self._lock:
                for client_ws in clients_to_remove:
                    if client_ws in self.active_websockets: self.active_websockets.remove(client_ws)

    def _process_user_data_message(self, msg: Dict[str, Any]):
        key_ref = self.stream_user_binance_api_key_ref[-4:] if self.stream_user_binance_api_key_ref and len(self.stream_user_binance_api_key_ref) >= 4 else 'N/A'
        self.logger.debug(f"WS UserMsg (User: {self.stream_user_id}, KeyRef: ...{key_ref}): {msg.get('e')}")
        event_type = msg.get('e')
        broadcast_msg = None

        if event_type == 'error':
            broadcast_msg = {"type": "error", "data": msg, "message": msg.get('m')}
        elif event_type == 'executionReport':
            order_id = str(msg.get('i')); status = msg.get('X')
            broadcast_msg = {'type': 'order_update', 'orderId': order_id, 'symbol': msg.get('s'),
                'side': msg.get('S'), 'orderType': msg.get('o'), 'status': status,
                'quantity': str(msg.get('q')), 'price': str(msg.get('p')),
                'executedQuantity': str(msg.get('z')), 'lastExecutedPrice': str(msg.get('L')),
                'commission': str(msg.get('n')) if msg.get('n') is not None else None,
                'commissionAsset': msg.get('N'), 'transactionTime': int(msg.get('T')),
                'orderTime': int(msg.get('O')) }
            if status == 'FILLED':
                if self.stream_user_id and self.stream_user_api_key_id is not None:
                    db: Optional[Session] = None
                    try:
                        db = SessionLocal()
                        avg_price = msg.get('ap', '0'); price_val = msg.get('L', '0')
                        if not avg_price or Decimal(avg_price) == Decimal('0'): avg_price = price_val
                        trade_input = {
                            "binance_order_id": order_id, "symbol": msg.get('s'),
                            "side": msg.get('S'), "order_type": msg.get('o'), "status": status,
                            "quantity_ordered": Decimal(str(msg.get('q'))), "quantity_filled": Decimal(str(msg.get('z'))),
                            "price_ordered": Decimal(str(msg.get('p'))) if msg.get('p') and msg.get('p') != '0' else None,
                            "price_avg_filled": Decimal(avg_price) if avg_price and avg_price != '0' else None,
                            "commission_amount": Decimal(str(msg.get('n'))) if msg.get('n') is not None else None,
                            "commission_asset": msg.get('N'),
                            "transaction_time": datetime.fromtimestamp(int(msg.get('T')) / 1000.0),
                            "user_api_key_id": self.stream_user_api_key_id,
                            "client_order_id": msg.get('c'), "time_in_force": msg.get('f'),
                            "notes": f"WS Log. OrderListId: {msg.get('g')}"}
                        trade_schema = TradeCreate(**trade_input)
                        if not trade_service.get_trade_by_binance_order_id(db, user_id=self.stream_user_id, binance_order_id=order_id):
                            trade_service.log_trade(db, user_id=self.stream_user_id, trade_data=trade_schema)
                            self.logger.info(f"Logged FILLED trade via WS: User {self.stream_user_id}, Order {order_id}")
                        else: self.logger.info(f"FILLED trade via WS already logged: User {self.stream_user_id}, Order {order_id}")
                    except Exception as e_log: self.logger.error(f"DB log error for FILLED order {order_id}: {e_log}", exc_info=True)
                    finally:
                        if db: db.close()
                else: self.logger.warning(f"FILLED Order {order_id} on WS, but no stream_user_id/api_key_id. Not logged.")
        elif event_type == 'outboundAccountPosition':
            balances = [{'asset':b.get('a'),'free':str(b.get('f','0')),'locked':str(b.get('l','0'))}
                        for b in msg.get('B',[]) if float(b.get('f','0'))>0 or float(b.get('l','0'))>0]
            if balances: broadcast_msg = {'type':'balance_update','balances':balances}
        if broadcast_msg:
            try:
                loop = asyncio.get_event_loop();
                if loop.is_running(): asyncio.run_coroutine_threadsafe(self.broadcast_to_clients(broadcast_msg), loop)
            except Exception as e_bc: self.logger.error(f"WS broadcast schedule error: {e_bc}", exc_info=True)

    async def start_user_data_stream(self, user_id: uuid.UUID, user_api_key_id: int, api_key: str, api_secret: str):
        async with self._lock:
            new_key_ref = api_key[-4:] if api_key and len(api_key) >=4 else "N/A"
            if self.user_data_stream_started and self.stream_user_binance_api_key_ref == new_key_ref and self.stream_user_id == user_id:
                self.stream_user_api_key_id = user_api_key_id; return
            if self.user_data_stream_started: await self._stop_twm_resources_locked()
            self.logger.info(f"Starting WS data stream for User {user_id}, UserAPIKey.id {user_api_key_id} (Key ...{new_key_ref})")
            try:
                self.stream_user_id, self.stream_user_api_key_id, self.stream_user_binance_api_key_ref = user_id, user_api_key_id, new_key_ref
                self.twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret, testnet=True)
                self.twm.start(); self.user_data_stream_key = self.twm.start_user_socket(callback=self._process_user_data_message)
                if self.user_data_stream_key: self.user_data_stream_started = True; self.logger.info(f"User Data Stream started for User {user_id}.")
                else: await self._stop_twm_resources_locked(); self.logger.error(f"Failed to start User Data Stream (no key) for User {user_id}.")
            except Exception as e: await self._stop_twm_resources_locked(); self.logger.error(f"Error starting User Data Stream for User {user_id}: {e}", exc_info=True)

    async def _stop_twm_resources_locked(self): # Assumes lock is held
        if self.twm:
            if self.user_data_stream_key:
                try: self.twm.stop_socket(self.user_data_stream_key)
                except Exception as e: self.logger.error(f"TWM stop_socket error: {e}")
            try: self.twm.join(timeout=1)
            except Exception as e: self.logger.error(f"TWM join error: {e}")
            self.twm = None
        self.user_data_stream_key, self.user_data_stream_started = None, False
        key_ref = self.stream_user_binance_api_key_ref[-4:] if self.stream_user_binance_api_key_ref and len(self.stream_user_binance_api_key_ref) >=4 else 'N/A'
        self.logger.info(f"TWM resources stopped for User {self.stream_user_id}, KeyRef ...{key_ref}")

    async def stop_user_data_stream(self): # Public method to stop and clear context
        async with self._lock:
            if not self.user_data_stream_started: return
            await self._stop_twm_resources_locked()
            self.stream_user_id, self.stream_user_api_key_id, self.stream_user_binance_api_key_ref = None, None, None
            self.logger.info("User stream context fully cleared after explicit stop.")

```

Now, for `trading_bot_backend/main.py`:
