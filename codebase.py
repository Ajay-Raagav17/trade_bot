import logging
import time
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from binance.streams import ThreadedWebsocketManager
from threading import Thread
import json
import random

class BasicBot:
    def __init__(self, api_key=None, api_secret=None, testnet=True):
        """Initialize the bot with API credentials"""
        # Use hardcoded credentials as defaults
        self.api_key = "hXAq4IlH3saKkJZLBkgutvCMGhPE1hQ8hLd1bH2LfUcF5tS2ZCe3sVAG3sCyc1vc"
        self.api_secret ="LXFYZET0FNFFTtnYLFLI6H2FgIlNk7ifdZsq9E5CUMeaFk3Coh4tl3yKfODWAi4V"
        
        # Override with provided credentials if they exist
        if api_key and api_secret:
            self.api_key = api_key
            self.api_secret = api_secret
            
        self.testnet = testnet
        self.client = None
        self.twm = None  
        self.ws_started = False
        self.setup_logger()
        
        # Always initialize the client
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Binance client with proper configuration"""
        try:
            def __init__(self, api_key, api_secret, testnet=False, production=True):
                self.testnet = testnet
                self.production = production
                

                # Modified client initialization for Spot Testnet
                try:
                    self.client = Client(
                        api_key, 
                        api_secret,
                        testnet=self.testnet,
                        tld='us' if self.production else 'testnet.binance.vision'
                    )
                except Exception as e:
                    self.log_and_print(f"Client initialization failed: {type(e).__name__} - {str(e)}", 'error')
                    if self.testnet:
                        # Set correct testnet URLs for Binance Spot
                        self.client.API_URL = 'https://testnet.binance.vision'
                        self.client.WEBSITE_URL = 'https://testnet.binance.vision'
                        self.client.FUTURES_API_URL = None  # Disable futures URLs
                        self.client.FUTURES_DATA_URL = None
                        self.client.FUTURES_COIN_URL = None
                    else:
                        # Production spot URLs
                        self.client.API_URL = 'https://api.binance.com'
                        self.client.WEBSITE_URL = 'https://www.binance.com'
                        self.client.FUTURES_API_URL = None
                        self.client.FUTURES_DATA_URL = None
                        self.client.FUTURES_COIN_URL = None
                    
                    # Test connection by getting exchange info
                    self.client.get_exchange_info()
                    self.log_and_print("Successfully connected to Binance Spot API")
                except Exception as e:
                    self.log_and_print(f"Failed to initialize client: {e}", 'error')
                    return False

    def setup_logger(self):
        """Setup logging configuration"""
        logging.basicConfig(
            filename='bot.log', 
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='a'
        )
        # Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)
    
    def log_and_print(self, message, level='info'):
        """Log message and print to console"""
        if level == 'info':
            logging.info(message)
            print(f"INFO: {message}")
        elif level == 'error':
            logging.error(message)
            print(f"ERROR: {message}")
        elif level == 'warning':
            logging.warning(message)
            print(f"WARNING: {message}")

    def get_account_balance(self):
        """Get account balance and positions"""
        try:
            max_retries = 3
            # Construct the full URL for the account endpoint
            account_url = f"{self.client.FUTURES_API_URL}/account"
            
            for attempt in range(max_retries):
                try:
                    # Use the lower-level _request method with the full URL
                    response = self.client._request('GET', account_url, True)
                    
                    # Log raw response for debugging
                    self.log_and_print(f"Raw response: {response}")
                    
                    # Check if the response is a dictionary and contains the expected key
                    if isinstance(response, dict) and 'totalWalletBalance' in response:
                        total_balance = float(response['totalWalletBalance'])
                        self.log_and_print(f"Account Balance: {total_balance} USDT")
                        return response
                    else:
                        # If response is not as expected, raise a KeyError or similar error
                        raise ValueError(f"Unexpected response structure: {response}")
                        
                except (BinanceAPIException, KeyError, ValueError) as e:
                    if attempt < max_retries - 1:
                        self.log_and_print(f"Attempt {attempt + 1} failed, retrying...", 'warning')
                        time.sleep(1)
                        continue
                    # Re-raise the exception after retries are exhausted
                    raise e
                    
        except BinanceAPIException as e:
            self.log_and_print(f"Binance API error: {e.message} (Code: {e.code})", 'error')
            if e.code == -2015:
                self.log_and_print("Invalid API-key, IP, or permissions for action", 'error')
            return None
        except Exception as e:
            self.log_and_print(f"Failed to get account info: {e}", 'error')
            return None

    def get_open_positions(self):
        """Get and display open positions"""
        try:
            account = self.client.futures_account()
            positions = [pos for pos in account['positions'] if float(pos['positionAmt']) != 0]
            
            if not positions:
                self.log_and_print("No open positions found.")
                return []
            
            self.log_and_print("Open Positions:")
            for pos in positions:
                pnl = float(pos['unrealizedPnl'])
                pnl_color = "+" if pnl >= 0 else ""
                self.log_and_print(
                    f"  {pos['symbol']}: {pos['positionAmt']} @ {pos['entryPrice']} "
                    f"| PnL: {pnl_color}{pnl:.4f} USDT"
                )
            return positions
            
        except Exception as e:
            self.log_and_print(f"Failed to get positions: {e}", 'error')
            return []

    def close_position(self, symbol, amount=None):
        """Close position (full or partial)"""
        try:
            # Get current position
            account = self.client.futures_account()
            position = None
            for pos in account['positions']:
                if pos['symbol'] == symbol.upper() and float(pos['positionAmt']) != 0:
                    position = pos
                    break
            
            if not position:
                self.log_and_print(f"No open position found for {symbol}", 'error')
                return False
            
            position_amt = float(position['positionAmt'])
            
            # Determine close amount and side
            if amount is None:
                close_qty = abs(position_amt)
            else:
                close_qty = min(amount, abs(position_amt))
            
            # Determine side (opposite of current position)
            close_side = 'SELL' if position_amt > 0 else 'BUY'
            
            # Place market order to close
            order = self.place_order(symbol, close_side, 'MARKET', close_qty)
            
            if order:
                self.log_and_print(f"Position closed: {close_qty} {symbol}")
                return True
            else:
                return False
                
        except Exception as e:
            self.log_and_print(f"Failed to close position: {e}", 'error')
            return False

    def manage_position(self, symbol, tp_percent=None, sl_percent=None, ts_percent=None):
        """Set up position management (TP/SL/Trailing Stop)"""
        try:
            # Get current position
            account = self.client.futures_account()
            position = None
            for pos in account['positions']:
                if pos['symbol'] == symbol.upper() and float(pos['positionAmt']) != 0:
                    position = pos
                    break
            
            if not position:
                self.log_and_print(f"No open position found for {symbol}", 'error')
                return False
            
            position_amt = float(position['positionAmt'])
            entry_price = float(position['entryPrice'])
            is_long = position_amt > 0
            
            orders_placed = []
            
            # Take Profit
            if tp_percent:
                tp_price = entry_price * (1 + tp_percent/100) if is_long else entry_price * (1 - tp_percent/100)
                tp_side = 'SELL' if is_long else 'BUY'
                tp_order = self.place_order(symbol, tp_side, 'LIMIT', abs(position_amt), price=tp_price)
                if tp_order:
                    orders_placed.append('TP')
            
            # Stop Loss
            if sl_percent:
                sl_price = entry_price * (1 - sl_percent/100) if is_long else entry_price * (1 + sl_percent/100)
                sl_side = 'SELL' if is_long else 'BUY'
                sl_order = self.place_order(symbol, sl_side, 'STOP_MARKET', abs(position_amt), stop_price=sl_price)
                if sl_order:
                    orders_placed.append('SL')
            
            self.log_and_print(f"Position management set: {', '.join(orders_placed)}")
            return len(orders_placed) > 0
            
        except Exception as e:
            self.log_and_print(f"Failed to set position management: {e}", 'error')
            return False

    def get_symbol_info(self, symbol):
        """Get symbol information for validation"""
        try:
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol.upper():
                    return s
            return None
        except Exception as e:
            self.log_and_print(f"Failed to get symbol info: {e}", 'error')
            return None

    def validate_order_params(self, symbol, side, order_type, quantity, price=None, stop_price=None):
        """Validate order parameters against symbol rules"""
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            return False, f"Symbol {symbol} not found or not active"
        
        # Check if symbol is active
        if symbol_info['status'] != 'TRADING':
            return False, f"Symbol {symbol} is not currently trading"
        
        # Validate quantity precision
        for filter_info in symbol_info['filters']:
            if filter_info['filterType'] == 'LOT_SIZE':
                min_qty = float(filter_info['minQty'])
                step_size = float(filter_info['stepSize'])
                if float(quantity) < min_qty:
                    return False, f"Quantity {quantity} is below minimum {min_qty}"
            
            if filter_info['filterType'] == 'PRICE_FILTER' and price:
                min_price = float(filter_info['minPrice'])
                tick_size = float(filter_info['tickSize'])
                if float(price) < min_price:
                    return False, f"Price {price} is below minimum {min_price}"
        
        return True, ""

    def place_order(self, symbol, side, order_type, quantity, price=None, stop_price=None, params=None):
        """Place a single order with comprehensive error handling"""
        try:
            # Validate parameters first
            valid, msg = self.validate_order_params(symbol, side, order_type, quantity, price, stop_price)
            if not valid:
                self.log_and_print(msg, 'error')
                return None

            order_params = {
                'symbol': symbol.upper(),
                'side': side.upper(),
                'type': order_type.upper(),
                'quantity': str(quantity)
            }
            
            if price and order_type.upper() in ['LIMIT', 'STOP_LIMIT']:
                order_params['price'] = str(price)
                order_params['timeInForce'] = 'GTC'  # Good till canceled for limit orders
            
            if stop_price and order_type.upper() in ['STOP_MARKET', 'STOP_LIMIT']:
                order_params['stopPrice'] = str(stop_price)
            
            if params:
                order_params.update(params)
            
            self.log_and_print(f"Placing order: {order_params}")
            order = self.client.futures_create_order(**order_params)
            self.log_and_print(f"Order placed successfully: {order['orderId']}")
            return order
            
        except BinanceAPIException as e:
            self.log_and_print(f"Binance API error: {e.message} (Code: {e.code})", 'error')
        except BinanceRequestException as e:
            self.log_and_print(f"Binance request error: {e}", 'error')
        except Exception as e:
            self.log_and_print(f"Unexpected error placing order: {e}", 'error')
        return None

    def place_grid_orders(self, symbol, side, total_quantity, start_price, end_price, grids):
        """Place grid trading orders with improved error handling"""
        try:
            self.log_and_print(f"Placing {grids} grid orders on {symbol}: {start_price} to {end_price}")
            
            if grids <= 1:
                self.log_and_print("Grid levels must be greater than 1", 'error')
                return None
                
            quantity_per_order = float(total_quantity) / grids
            price_step = (float(end_price) - float(start_price)) / (grids - 1) if grids > 1 else 0
            
            orders = []
            failed_orders = 0
            
            for i in range(grids):
                current_price = float(start_price) + (i * price_step)
                # Round price to appropriate decimal places
                current_price = round(current_price, 4)
                
                order = self.place_order(symbol, side, 'LIMIT', quantity_per_order, price=current_price)
                if order:
                    orders.append(order)
                    self.log_and_print(f"Grid order {i+1}/{grids} placed at {current_price}")
                else:
                    failed_orders += 1
                    self.log_and_print(f"Failed to place grid order {i+1} at price {current_price}", 'error')
                
                # Rate limiting delay
                time.sleep(0.5)
            
            success_count = len(orders)
            self.log_and_print(f"Grid orders completed: {success_count}/{grids} successful, {failed_orders} failed")
            return orders
            
        except Exception as e:
            self.log_and_print(f"Grid order error: {e}", 'error')
            return None

    def place_twap_order(self, symbol, side, quantity, duration_min, intervals):
        """Time-Weighted Average Price order execution with improved timing and delays"""
        try:
            if intervals <= 0 or duration_min <= 0:
                self.log_and_print("Duration and intervals must be positive", 'error')
                return None
                
            interval_seconds = (duration_min * 60) / intervals
            chunk_size = float(quantity) / intervals
            
            # Normalize inputs
            symbol = symbol.upper()
            side = side.upper()
            
            self.log_and_print(f"Starting TWAP execution: {quantity} {symbol} over {duration_min} minutes in {intervals} intervals")
            self.log_and_print(f"Each order: {chunk_size}, Interval: {interval_seconds} seconds")
            
            orders = []
            for i in range(intervals):
                self.log_and_print(f"TWAP order {i+1}/{intervals}")
                
                # Add random delay (0.1-0.5s) to avoid exact timing patterns
                time.sleep(0.1 + (0.4 * random.random()))
                
                order = self.place_order(symbol, side, 'MARKET', chunk_size)
                if order:
                    orders.append(order)
                else:
                    self.log_and_print(f"Failed to place TWAP order {i+1}", 'error')
                
                # Sleep between orders (except for the last one)
                if i < intervals - 1:
                    # Add small random variation to interval timing
                    sleep_time = interval_seconds * (0.95 + (0.1 * random.random()))
                    time.sleep(sleep_time)
            
            self.log_and_print(f"TWAP execution completed: {len(orders)}/{intervals} orders placed")
            return orders
            
        except Exception as e:
            self.log_and_print(f"TWAP order error: {e}", 'error')
            return None

    def validate_input(self, side, order_type, quantity, price=None, stop_price=None):
        """Validate user input parameters"""
        valid_sides = ['BUY', 'SELL']
        valid_order_types = ['MARKET', 'LIMIT', 'STOP_MARKET', 'STOP_LIMIT', 'TWAP', 'GRID']
        
        if side.upper() not in valid_sides:
            return False, "Side must be BUY or SELL."
        
        if order_type.upper() not in valid_order_types:
            return False, f"Order type must be one of {valid_order_types}."
        
        try:
            qty_val = float(quantity)
            if qty_val <= 0:
                return False, "Quantity must be positive."
                
            if price:
                price_val = float(price)
                if price_val <= 0:
                    return False, "Price must be positive."
                    
            if stop_price:
                stop_val = float(stop_price)
                if stop_val <= 0:
                    return False, "Stop price must be positive."
                    
        except ValueError:
            return False, "Quantity, price, and stop price must be numeric."
        
        return True, ""

    def start_websocket(self, symbol):
        """Initialize WebSocket connections for real-time data"""
        try:
            if not self.client:
                self.log_and_print("Client not initialized", 'error')
                return False

            # Normalize symbol casing early
            symbol = symbol.upper()
            
            # Configure WebSocket URLs based on testnet setting
            ws_url = 'wss://stream.testnet.binance.vision/ws' if self.testnet else 'wss://stream.binance.com/ws'
            ws_api_url = 'wss://ws-api.testnet.binance.vision/ws-api/v3' if self.testnet else 'wss://ws-api.binance.com/ws-api/v3'
                
            self.twm = ThreadedWebsocketManager(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet,
                websocket_url=ws_url,
                api_url=ws_api_url
            )
            self.twm.start()
            
            # Start user data stream with fallback logic
            try:
                self.twm.start_futures_socket(callback=self.handle_socket_message)
            except Exception as e:
                self.log_and_print(f"Failed to start user data stream: {e}", 'error')
            
            # Start symbol ticker stream with fallback logic
            try:
                self.twm.start_futures_symbol_ticker_socket(
                    callback=self.handle_ticker_message,
                    symbol=symbol
                )
            except Exception as e:
                self.log_and_print(f"Failed to start ticker stream: {e}", 'error')
                return False
            
            self.ws_started = True
            self.log_and_print(f"WebSocket started for {symbol}")
            return True
            
        except Exception as e:
            self.log_and_print(f"WebSocket start error: {e}", 'error')
            return False

    def handle_socket_message(self, msg):
        """Handle real-time user data updates with improved error handling"""
        try:
            if not msg:
                return

            event_type = msg.get('e')
            if event_type == 'ORDER_TRADE_UPDATE':
                order_data = msg.get('o', {})
                symbol = order_data.get('s', '').upper()
                status = order_data.get('X', '')
                side = order_data.get('S', '')
                quantity = order_data.get('q', '0')

                self.log_and_print(
                    f"Order update - Symbol: {symbol}, "
                    f"Status: {status}, "
                    f"Side: {side}, "
                    f"Quantity: {quantity}"
                )
        except Exception as e:
            self.log_and_print(f"Socket message handling error: {e}", 'error')

    def handle_ticker_message(self, msg):
        """Handle real-time price updates with improved formatting"""
        try:
            if not msg:
                return

            symbol = msg.get('s', '').upper()
            price = msg.get('c', '0')
            if symbol and price:
                formatted_price = f"{float(price):.8f}".rstrip('0').rstrip('.')
                print(f"{symbol}: {formatted_price}")
        except Exception as e:
            self.log_and_print(f"Ticker message handling error: {e}", 'error')

    def stop_websocket(self):
        """Stop WebSocket connections"""
        if self.twm:
            self.twm.stop()
            self.ws_started = False
            self.log_and_print("WebSocket stopped")

    def run(self):
        """Main bot execution loop"""
        print("=" * 60)
        print("Welcome to BasicBot - Binance Futures Trading Bot")
        print("=" * 60)
        
        # Check API credentials first
        if not self.api_key or not self.api_secret:
            self.log_and_print("API credentials are empty. Please set your API key and secret.", 'error')
            return
        
        # Verify the client is initialized
        if not self.client:
            if not self._initialize_client():
                print("Failed to initialize client. Please check your credentials and internet connection.")
                return
        
        # Show account info
        account = self.get_account_balance()
        if not account:
            print("Failed to retrieve account information. Please check your API credentials.")
            return
        
        try:
            while True:
                print("\n" + "-" * 40)
                print("Select an action:")
                print("1. Place a new order")
                print("2. View open positions")
                print("3. Manage existing position")
                print("4. Close a position")
                print("5. Exit")
                
                choice = input("Enter your choice (1-5): ").strip()
                
                if choice == "1":
                    # Place new order
                    symbol = input("Enter trading pair symbol (e.g. BTCUSDT): ").strip().upper()
                    if not symbol:
                        continue
                        
                    side = input("Enter side (BUY/SELL): ").strip().upper()
                    order_type = input("Enter order type (MARKET, LIMIT, STOP_MARKET, STOP_LIMIT, TWAP, GRID): ").strip().upper()
                    quantity = input("Enter quantity: ").strip()
                    
                    price = None
                    stop_price = None
                    
                    # Get additional parameters based on order type
                    if order_type in ['LIMIT', 'STOP_LIMIT', 'GRID']:
                        price = input("Enter price (for GRID, enter start price): ").strip()
                        
                    if order_type in ['STOP_MARKET', 'STOP_LIMIT']:
                        stop_price = input("Enter stop price: ").strip()
                    
                    # Validate basic input
                    valid, msg = self.validate_input(side, order_type, quantity, price, stop_price)
                    if not valid:
                        print(f"Input error: {msg}")
                        continue

                    # Execute different order types
                    if order_type == 'GRID':
                        end_price = input("Enter end price for grid: ").strip()
                        grids = input("Enter number of grid levels: ").strip()
                        try:
                            grids = int(grids)
                            result = self.place_grid_orders(symbol, side, float(quantity), 
                                                          float(price), float(end_price), grids)
                        except ValueError:
                            print("Grid levels must be a number")
                            continue
                            
                    elif order_type == 'TWAP':
                        duration = input("Enter duration in minutes: ").strip()
                        intervals = input("Enter number of intervals: ").strip()
                        try:
                            duration = float(duration)
                            intervals = int(intervals)
                            result = self.place_twap_order(symbol, side, float(quantity), duration, intervals)
                        except ValueError:
                            print("Duration and intervals must be numbers")
                            continue
                            
                    else:
                        # Standard order types
                        result = self.place_order(symbol, side, order_type, float(quantity), 
                                                    price=float(price) if price else None, 
                                                    stop_price=float(stop_price) if stop_price else None)
                    
                    if result:
                        print("✓ Order(s) placed successfully!")
                        manage = input("Set up position management? (yes/no): ").strip().lower()
                        if manage in ["yes", "y"]:
                            tp_percent = input("Take profit percentage (0 for none): ").strip()
                            sl_percent = input("Stop loss percentage (0 for none): ").strip()
                            ts_percent = input("Trailing stop percentage (0 for none): ").strip()
                            
                            try:
                                tp_percent = float(tp_percent) if tp_percent and float(tp_percent) > 0 else None
                                sl_percent = float(sl_percent) if sl_percent and float(sl_percent) > 0 else None
                                ts_percent = float(ts_percent) if ts_percent and float(ts_percent) > 0 else None
                                
                                if self.manage_position(symbol, tp_percent, sl_percent, ts_percent):
                                    print("✓ Position management set up successfully!")
                            except ValueError:
                                print("Invalid percentage values")
                    else:
                        print("✗ Order placement failed.")
                    
                elif choice == "2":
                    # View open positions
                    self.get_open_positions()
                
                elif choice == "3":
                    # Manage existing position
                    symbol = input("Enter symbol to manage (e.g. BTCUSDT): ").strip().upper()
                    if not symbol:
                        continue
                        
                    tp_percent = input("Take profit percentage (0 for none): ").strip()
                    sl_percent = input("Stop loss percentage (0 for none): ").strip()
                    ts_percent = input("Trailing stop percentage (0 for none): ").strip()
                    
                    try:
                        tp_percent = float(tp_percent) if tp_percent and float(tp_percent) > 0 else None
                        sl_percent = float(sl_percent) if sl_percent and float(sl_percent) > 0 else None
                        ts_percent = float(ts_percent) if ts_percent and float(ts_percent) > 0 else None
                        
                        if self.manage_position(symbol, tp_percent, sl_percent, ts_percent):
                            print("✓ Position management updated successfully!")
                        else:
                            print("✗ Failed to update position management")
                    except ValueError:
                        print("Invalid percentage values")
                
                elif choice == "4":
                    # Close a position
                    symbol = input("Enter symbol to close (e.g. BTCUSDT): ").strip().upper()
                    if not symbol:
                        continue
                        
                    partial = input("Close partially? (yes/no): ").strip().lower()
                    amount = None
                    if partial in ["yes", "y"]:
                        amount_str = input("Enter amount to close: ").strip()
                        try:
                            amount = float(amount_str)
                        except ValueError:
                            print("Invalid amount")
                            continue
                    
                    if self.close_position(symbol, amount):
                        print("✓ Position closed successfully!")
                    else:
                        print("✗ Failed to close position")
                
                elif choice == "5":
                    break
                
                else:
                    print("Invalid choice. Please enter a number between 1 and 5.")
                
        except KeyboardInterrupt:
            print("\n\nBot interrupted by user.")
        except Exception as e:
            self.log_and_print(f"Unexpected error in main loop: {e}", 'error')
        finally:
            self.stop_websocket()
            print("Exiting BasicBot. Goodbye!")

if __name__ == '__main__':
    bot = BasicBot(testnet=True)  # Make sure to add your API credentials
    bot.run()