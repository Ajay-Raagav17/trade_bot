# trading_bot_backend/bot/bot_logic.py
import logging
import time
import os
import asyncio # Added
from typing import List, Any, Dict, Optional # Consolidated and added Optional, Dict

from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance import ThreadedWebsocketManager # Added

try:
    from .env import API_KEY, API_SECRET
except ImportError:
    from env import API_KEY, API_SECRET # type: ignore

# Module-level logger configuration is handled in main.py to avoid multiple basicConfig calls.
# BasicBot will use a child logger.

DEFAULT_SYMBOL = "BTCUSDT"
MAX_RETRIES = 3

class BasicBot:
    def __init__(self):
        self.logger = logging.getLogger("trading_bot_api.BasicBot") # Child logger

        if not API_KEY or not API_SECRET:
            self.logger.error("API credentials are required but not found.")
            raise ValueError("API credentials are required. Please set them in env.py or as environment variables.")

        self.client = Client(API_KEY, API_SECRET, testnet=True)
        self.logger.info("BasicBot initialized with Spot Testnet configuration.")

        self.twm: Optional[ThreadedWebsocketManager] = None
        self.user_data_stream_key: Optional[str] = None
        self.active_websockets: List[Any] = [] # Stores FastAPI WebSocket objects
        self.user_data_stream_started: bool = False
        self._lock = asyncio.Lock() # For concurrent access to shared WS resources

    def verify_spot_access(self): # This remains synchronous
        try:
            account_info = self.client.get_account()
            if account_info.get('canTrade'):
                self.logger.info("Successfully verified spot trading access.")
                return {"status": "success", "message": "Spot trading access verified."}
            else:
                self.logger.error("Spot trading is not enabled for this account.")
                raise Exception("Spot trading not enabled for this account.")
        except BinanceAPIException as e:
            self.logger.error(f"Failed to verify spot trading access: {e}", exc_info=True)
            raise Exception(f"API Error: Failed to verify spot trading access: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error during spot access verification: {e}", exc_info=True)
            raise Exception(f"Unexpected error verifying spot access: {str(e)}")

    def get_account_info(self): # Synchronous
        try:
            account_info = self.client.get_account()
            non_zero_balances = [{
                'asset': balance['asset'],
                'free': float(balance['free']),
                'locked': float(balance['locked'])
            } for balance in account_info['balances']
                if float(balance['free']) > 0 or float(balance['locked']) > 0]
            return {"status": "success", "balances": non_zero_balances}
        except BinanceAPIException as e:
            self.logger.error(f"Failed to fetch account info: {str(e)}", exc_info=True)
            raise Exception(f"API Error: Failed to fetch account info: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error fetching account info: {e}", exc_info=True)
            raise Exception(f"Unexpected error fetching account info: {str(e)}")

    def get_symbol_info(self, symbol: str): # Synchronous
        try:
            symbol_info = self.client.get_symbol_info(symbol)
            if not symbol_info:
                 raise ValueError(f"Trading pair {symbol} not found")
            return {"status": "success", "data": symbol_info}
        except BinanceAPIException as e:
            self.logger.error(f"Failed to fetch symbol info for {symbol}: {str(e)}", exc_info=True)
            raise Exception(f"API Error: Failed to fetch info for {symbol}: {str(e)}")
        except ValueError as e:
            self.logger.warning(f"Value error fetching symbol info for {symbol}: {str(e)}")
            raise e
        except Exception as e:
            self.logger.error(f"Unexpected error fetching symbol info for {symbol}: {e}", exc_info=True)
            raise Exception(f"Unexpected error fetching info for {symbol}: {str(e)}")

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: float = None, stop_price: float = None): # Synchronous
        try:
            symbol_data = self.client.get_symbol_info(symbol)
            if not symbol_data:
                raise ValueError(f"Trading pair {symbol} not found")

            # Placeholder for detailed validation logic (LOT_SIZE, MIN_NOTIONAL, PRICE_FILTER)
            # Ensure quantity and price are formatted according to symbol rules using symbol_data['filters']

            order_params = {
                'symbol': symbol.upper(), 'side': side.upper(), 'quantity': quantity
            }
            order_type_upper = order_type.upper()

            if order_type_upper == ORDER_TYPE_MARKET:
                order_params['type'] = ORDER_TYPE_MARKET
            elif order_type_upper == ORDER_TYPE_LIMIT:
                if price is None: raise ValueError("Price is required for LIMIT orders.")
                order_params.update({'type': ORDER_TYPE_LIMIT, 'timeInForce': TIME_IN_FORCE_GTC, 'price': self.client.format_price(symbol=symbol, price=price)})
            elif order_type_upper == 'STOP_MARKET' or order_type_upper in [ORDER_TYPE_STOP_LOSS, ORDER_TYPE_STOP_LOSS_LIMIT, ORDER_TYPE_TAKE_PROFIT, ORDER_TYPE_TAKE_PROFIT_LIMIT]:
                order_params['type'] = ORDER_TYPE_STOP_LOSS if order_type_upper == 'STOP_MARKET' else order_type_upper
                if stop_price is None: raise ValueError("Stop price is required for this order type.")
                order_params['stopPrice'] = self.client.format_price(symbol=symbol, price=stop_price)
                if order_type_upper in [ORDER_TYPE_STOP_LOSS_LIMIT, ORDER_TYPE_TAKE_PROFIT_LIMIT]:
                    if price is None: raise ValueError("Price is required for LIMIT-based stop/take profit orders.")
                    order_params['price'] = self.client.format_price(symbol=symbol, price=price)
                    order_params['timeInForce'] = TIME_IN_FORCE_GTC
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            # Placeholder for MIN_NOTIONAL check

            self.logger.info(f"Attempting to place order with params: {order_params}")
            new_order = self.client.create_order(**order_params)
            self.logger.info(f"Order placed successfully: ID {new_order.get('orderId')}, Symbol {new_order.get('symbol')}, Status {new_order.get('status')}")
            return {"status": "success", "order": new_order}
        except BinanceAPIException as e:
            self.logger.error(f"Binance API Error placing order for {symbol}: {str(e)} - Code: {e.code}, Message: {e.message}", exc_info=True)
            raise Exception(f"Binance API Error ({e.code}): {e.message}")
        except ValueError as e:
            self.logger.warning(f"Validation Error placing order for {symbol}: {str(e)}", exc_info=True)
            raise Exception(f"Validation Error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error placing order for {symbol}: {str(e)}", exc_info=True)
            raise Exception(f"Unexpected Server Error: {str(e)}")

    def twap(self, symbol, side, total_qty, interval_sec, slices): # Synchronous
        try:
            placed_orders = []
            if slices <= 0: raise ValueError("Number of slices must be greater than 0.")
            if total_qty <= 0: raise ValueError("Total quantity must be greater than 0.")
            if interval_sec <= 0: raise ValueError("Interval must be greater than 0.")
            qty_per_order = round(total_qty / slices, 8) # TODO: Adjust precision based on symbol rules
            self.logger.info(f"Starting TWAP strategy: symbol={symbol}, side={side}, total_qty={total_qty}, slices={slices}, interval={interval_sec}s, qty_per_slice={qty_per_order}")
            for i in range(slices):
                self.logger.info(f"TWAP: Executing slice {i+1}/{slices} for {qty_per_order} {symbol}")
                try:
                    order_result = self.place_order(symbol, side, 'MARKET', qty_per_order)
                    if order_result and order_result.get('status') == 'success' and order_result.get('order'):
                        placed_orders.append(order_result['order'])
                        self.logger.info(f"TWAP slice {i+1}/{slices}: Order {order_result['order'].get('orderId')} placed.")
                    else:
                        error_detail = f"TWAP slice {i+1}/{slices}: Failed to place order or unexpected result. Result: {order_result}"
                        self.logger.error(error_detail)
                        raise Exception(error_detail)
                except Exception as slice_e:
                    self.logger.error(f"TWAP slice {i+1}/{slices} for {qty_per_order} {symbol} failed: {slice_e}", exc_info=True)
                    raise Exception(f"TWAP strategy failed at slice {i+1}/{slices}. Error: {slice_e}")
                if i < slices - 1:
                    self.logger.info(f"TWAP: Sleeping for {interval_sec} seconds before next slice.")
                    time.sleep(interval_sec)
            self.logger.info(f"TWAP strategy execution completed for {symbol}. Placed {len(placed_orders)} orders.")
            return {'status': 'success', 'message': 'TWAP execution completed successfully.', 'orders_placed': placed_orders}
        except ValueError as ve:
            self.logger.warning(f"TWAP strategy validation error for {symbol}: {ve}", exc_info=True)
            raise ve
        except Exception as e:
            self.logger.error(f"TWAP strategy failed for {symbol}: {str(e)}", exc_info=True)
            raise e

    def grid(self, symbol, lower_price, upper_price, grids, quantity, side): # Synchronous
        try:
            placed_orders = []
            if grids <= 1: raise ValueError("Number of grid levels must be at least 2.")
            if lower_price >= upper_price: raise ValueError("Lower price must be less than upper price.")
            if quantity <= 0: raise ValueError("Quantity per grid must be greater than 0.")
            price_step = (upper_price - lower_price) / (grids - 1)
            self.logger.info(f"Starting Grid: {symbol}, side={side}, range=[{lower_price}-{upper_price}], grids={grids}, qty_per_grid={quantity}, step={price_step}")
            for i in range(grids):
                price = round(lower_price + i * price_step, 8) # TODO: Adjust precision based on symbol rules
                self.logger.info(f"Grid: Placing LIMIT {side} order {i+1}/{grids} at price {price} for {quantity} {symbol}")
                try:
                    order_result = self.place_order(symbol, side, 'LIMIT', quantity, price=price)
                    if order_result and order_result.get('status') == 'success' and order_result.get('order'):
                        placed_orders.append(order_result['order'])
                        self.logger.info(f"Grid order {i+1}/{grids}: ID {order_result['order'].get('orderId')} placed at {price}.")
                    else:
                        error_detail = f"Grid order {i+1}/{grids}: Failed to place order at {price}. Result: {order_result}"
                        self.logger.error(error_detail)
                        raise Exception(error_detail)
                except Exception as slice_e:
                    self.logger.error(f"Grid order {i+1}/{grids} at {price} for {quantity} {symbol} failed: {slice_e}", exc_info=True)
                    raise Exception(f"Grid strategy failed at order {i+1}/{grids} (price {price}). Error: {slice_e}")
            self.logger.info(f"Grid setup completed for {symbol}. Placed {len(placed_orders)} orders.")
            return {'status': 'success', 'message': 'Grid setup completed successfully.', 'orders_placed': placed_orders}
        except ValueError as ve:
            self.logger.warning(f"Grid strategy validation error for {symbol}: {ve}", exc_info=True)
            raise ve
        except Exception as e:
            self.logger.error(f"Grid strategy failed for {symbol}: {str(e)}", exc_info=True)
            raise e

    # --- WebSocket Management Methods ---
    async def add_websocket_client(self, websocket: Any): # Param type is FastAPI's WebSocket
        async with self._lock:
            if websocket not in self.active_websockets:
                self.active_websockets.append(websocket)
                self.logger.info(f"WebSocket client added. Total clients: {len(self.active_websockets)}")
        if len(self.active_websockets) == 1 and not self.user_data_stream_started: # If first client
            await self.start_user_data_stream()

    async def remove_websocket_client(self, websocket: Any):
        async with self._lock:
            if websocket in self.active_websockets:
                self.active_websockets.remove(websocket)
                self.logger.info(f"WebSocket client removed. Total clients: {len(self.active_websockets)}")
        if not self.active_websockets and self.user_data_stream_started: # If last client
            self.logger.info("No active WebSocket clients left. Stopping user data stream.")
            await self.stop_user_data_stream()

    async def broadcast_to_clients(self, message_data: Dict[str, Any]):
        if not self.active_websockets: return
        self.logger.debug(f"Broadcasting to {len(self.active_websockets)} clients: {message_data}")
        clients_to_remove = []
        for client_ws in list(self.active_websockets): # Iterate over a copy for safe removal
            try:
                await client_ws.send_json(message_data)
            except Exception as e: # Catches WebSocketDisconnect, ConnectionClosed, etc.
                self.logger.error(f"Error sending to client {client_ws}: {e}. Marking for removal.")
                clients_to_remove.append(client_ws)
        if clients_to_remove:
            async with self._lock:
                for client_ws in clients_to_remove:
                    if client_ws in self.active_websockets: self.active_websockets.remove(client_ws)
                self.logger.info(f"Removed {len(clients_to_remove)} unresponsive/disconnected WebSocket clients.")

    def _process_user_data_message(self, msg: Dict[str, Any]):
        self.logger.debug(f"User stream raw msg in TWM thread: {msg}")
        event_type = msg.get('e')
        processed_message = None
        if event_type == 'error':
            self.logger.error(f"User data stream error (Binance): {msg.get('m')}")
            processed_message = {"type": "error", "data": msg}
        elif event_type == 'executionReport':
            self.logger.info(f"Processing executionReport: OrderID {msg.get('i')}, Symbol {msg.get('s')}, Status {msg.get('X')}")
            processed_message = {
                'type': 'order_update', 'orderId': msg.get('i'), 'symbol': msg.get('s'),
                'side': msg.get('S'), 'orderType': msg.get('o'), 'status': msg.get('X'),
                'quantity': msg.get('q'), 'price': msg.get('p'),
                'executedQuantity': msg.get('z'), 'lastExecutedPrice': msg.get('L'),
                'commission': msg.get('n'), 'commissionAsset': msg.get('N'),
                'transactionTime': msg.get('T'), 'orderTime': msg.get('O')
            }
        elif event_type == 'outboundAccountPosition':
            self.logger.info("Processing outboundAccountPosition (balance update).")
            active_balances = [
                {'asset': b.get('a'), 'free': b.get('f'), 'locked': b.get('l')}
                for b in msg.get('B', [])
                if float(b.get('f',0.0)) > 0 or float(b.get('l',0.0)) > 0
            ]
            if active_balances:
                 processed_message = {'type': 'balance_update', 'balances': active_balances}
            else:
                self.logger.debug("Balance update received, but no non-zero balances to report.")

        if processed_message:
            try:
                loop = asyncio.get_event_loop() # Get main thread's event loop
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.broadcast_to_clients(processed_message), loop)
                else:
                    self.logger.warning("Main event loop not running. Cannot broadcast from TWM.")
            except RuntimeError: # If called from a thread without a current event loop set by asyncio.set_event_loop()
                 self.logger.error("RuntimeError: No current event loop in TWM thread for broadcast scheduling.")
            except Exception as e_broadcast:
                self.logger.error(f"Exception during TWM message broadcast scheduling: {e_broadcast}", exc_info=True)

    async def start_user_data_stream(self):
        async with self._lock:
            if self.user_data_stream_started:
                self.logger.info("User data stream start requested, but already running.")
                return
            self.logger.info("Attempting to start Binance User Data Stream...")
            try:
                if self.twm is not None: # Should ideally be None here
                    self.logger.warning("TWM instance found during start. Attempting to stop old one.")
                    self.twm.stop(); self.twm.join(timeout=2)

                self.twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET, testnet=True)
                self.twm.start() # Starts the TWM's own processing thread
                self.user_data_stream_key = self.twm.start_user_socket(callback=self._process_user_data_message)

                if self.user_data_stream_key:
                    self.user_data_stream_started = True
                    self.logger.info(f"User Data Stream started successfully. Stream Key: {self.user_data_stream_key}")
                else:
                    self.logger.error("Failed to start User Data Stream: TWM did not return a stream key.")
                    if self.twm: self.twm.stop(); self.twm = None # Clean up TWM
            except Exception as e:
                self.logger.error(f"Error starting User Data Stream: {e}", exc_info=True)
                if self.twm: self.twm.stop(); self.twm = None
                self.user_data_stream_started = False

    async def stop_user_data_stream(self):
        async with self._lock:
            if not self.user_data_stream_started or not self.twm:
                self.logger.info("User data stream stop requested, but not running or TWM not initialized.")
                return

            self.logger.info(f"Attempting to stop User Data Stream: {self.user_data_stream_key}...")
            try:
                if self.user_data_stream_key:
                    stopped = self.twm.stop_socket(self.user_data_stream_key)
                    self.logger.info(f"TWM stop_socket call for {self.user_data_stream_key} returned: {stopped}")

                self.twm.join(timeout=5) # Wait for TWM thread to finish

                self.user_data_stream_key = None
                self.user_data_stream_started = False
                self.twm = None # Clear the TWM instance
                self.logger.info("User Data Stream stopped and TWM instance cleared.")
            except Exception as e:
                self.logger.error(f"Error stopping User Data Stream or TWM: {e}", exc_info=True)
                # Mark as not started even if there was an error during stop
                self.user_data_stream_started = False
                self.twm = None
```
