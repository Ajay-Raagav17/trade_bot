import logging, time, os
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance import ThreadedWebsocketManager
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.logging import RichHandler
from rich import print as rprint
from datetime import datetime
# Add this import for trade_records
from trade_records import log_order, log_error

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        RichHandler(console=console, rich_tracebacks=True)
    ]
)

logger = logging.getLogger("trading_bot")
try:
    from env import API_KEY, API_SECRET
except ImportError:
    load_dotenv()
    API_KEY = os.getenv('BINANCE_API_KEY')
    API_SECRET = os.getenv('BINANCE_API_SECRET')
if not API_KEY or not API_SECRET:
    raise ValueError("API credentials are required. Please set them in env.py or as environment variables.")
DEFAULT_SYMBOL = "BTCUSDT"  # Default trading pair
DEFAULT_TRADE_SIZE = 0.001   # Default trade quantity
MAX_RETRIES = 3              # Maximum retry attempts for API calls

TRADING_PAIRS = {
    'BTC': 'BTCUSDT',
    'ETH': 'ETHUSDT',
    'BNB': 'BNBUSDT',
    'XRP': 'XRPUSDT',
    'SOL': 'SOLUSDT',
    'ADA': 'ADAUSDT',
    'DOT': 'DOTUSDT',
    'DOGE': 'DOGEUSDT',
    'MATIC': 'MATICUSDT',
    'LINK': 'LINKUSDT'
}

STATUS_EMOJIS = {
    'NEW': '🆕',
    'PARTIALLY_FILLED': '⏳',
    'FILLED': '✅',
    'EXECUTED': '✅',
    'CANCELED': '❌',
    'REJECTED': '⛔',
    'EXPIRED': '⏰'
}

class BasicBot:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.client.API_URL = 'https://testnet.binance.vision/api'
        self.twm = ThreadedWebsocketManager(
            api_key=api_key,
            api_secret=api_secret,
            testnet=True
        )
        self.twm.start()
        console.print("Bot initialized with spot testnet configuration")
        self.verify_spot_access()

    def place_order(self, symbol, side, order_type, quantity, price=None, stop_price=None):
        try:
            symbol_info = self.client.get_symbol_info(symbol)
            if not symbol_info:
                console.print(f"[red]Error: Trading pair {symbol} not found[/red]")
                return None
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
            price_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER'), None)
            if lot_size_filter:
                min_qty = float(lot_size_filter['minQty'])
                max_qty = float(lot_size_filter['maxQty'])
                step_size = float(lot_size_filter['stepSize'])
                
                if quantity < min_qty:
                    console.print(f"[red]Error: Quantity {quantity} is below minimum allowed ({min_qty})[/red]")
                    return None
                if quantity > max_qty:
                    console.print(f"[red]Error: Quantity {quantity} is above maximum allowed ({max_qty})[/red]")
                    return None
            if order_type == 'LIMIT':
                if price_filter:
                    min_price = float(price_filter['minPrice'])
                    max_price = float(price_filter['maxPrice'])
                    tick_size = float(price_filter['tickSize'])
                    
                    if price < min_price:
                        console.print(f"[red]Error: Price {price} is below minimum allowed ({min_price})[/red]")
                        return None
                    if price > max_price:
                        console.print(f"[red]Error: Price {price} is above maximum allowed ({max_price})[/red]")
                        return None
                    price_deviation = abs(price - current_price) / current_price
                    if price_deviation > 0.20:  # 20% deviation threshold
                        console.print(f"[yellow]Warning: Price {price} is {price_deviation*100:.1f}% away from current market price ({current_price})[/yellow]")
                        if not Confirm.ask("Do you want to continue with this price?"):
                            return None
            if notional_filter:
                min_notional = float(notional_filter['minNotional'])
                order_value = quantity * (price or current_price)
                print(f"Debug: Order value = {order_value}, Min notional = {min_notional}")  # Debug print
                
                if order_value < min_notional:
                    print(f"Debug: Order value too small, showing panel")  # Debug print
                    min_qty = 5.0 / (price or current_price)  # Using fixed 5 USDT minimum
                    console.print(Panel(
                        f"[red]❌ Order value (${order_value:.2f} USDT) is too small[/red]\n" +
                        f"[white]Binance requires minimum trade value of $5.00 USDT[/white]\n" +
                        f"[yellow]Your order value: {quantity} {symbol_info['baseAsset']} × ${price or current_price:.4f} = ${order_value:.2f} USDT[/yellow]\n" +
                        f"[green]💡 Suggested minimum quantity: {min_qty:.6f} {symbol_info['baseAsset']}[/green]",
                        title="⚠️ Minimum Trade Value Not Met",
                        border_style="red"
                    ))
                    print("Debug: Panel should be displayed")  # Debug print
                    return None

            # Proceed with order placement
            order_params = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity
            }
            
            logger.info(f"Placing {order_type} order - Symbol: {symbol}, Side: {side}, Quantity: {quantity}")
            log_order(order_type, symbol, side, quantity, price)
            
            with console.status(f"[bold blue]Placing order...") as status:
                if order_type == 'MARKET':
                    order_params['type'] = ORDER_TYPE_MARKET
                elif order_type == 'LIMIT':
                    order_params.update({
                        'type': ORDER_TYPE_LIMIT,
                        'timeInForce': TIME_IN_FORCE_GTC,
                        'price': price
                    })
                elif order_type == 'STOP_MARKET':
                    order_params.update({
                        'type': ORDER_TYPE_STOP_LOSS,
                        'stopPrice': stop_price
                    })
                
                order = self.client.create_order(**order_params)
                timestamp = datetime.fromtimestamp(int(order['transactTime']) / 1000)
                
                log_order(order_type, symbol, side, quantity, price, order.get('status'), order.get('orderId'))
                
                # Show success message with order details
                table = Table(title=f"✅ Order Placed Successfully - {timestamp.strftime('%H:%M:%S')}")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Order ID", str(order['orderId']))
                table.add_row("Symbol", symbol)
                table.add_row("Type", order_type)
                table.add_row("Side", side)
                table.add_row("Quantity", str(quantity))
                if price:
                    table.add_row("Price", str(price))
                if stop_price:
                    table.add_row("Stop Price", str(stop_price))
                table.add_row("Status", order.get('status', 'PENDING'))
                
                console.print(table)
                return order
                
        except BinanceAPIException as e:
            error_msg = str(e)
            if "MIN_NOTIONAL" in error_msg:
                # Get current price for calculation
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                order_value = quantity * current_price
                min_qty = 5.0 / current_price  # Using fixed 5 USDT minimum
                
                console.print(Panel(
                    f"[red]❌ Order value (${order_value:.2f} USDT) is too small[/red]\n" +
                    f"[white]Binance requires minimum trade value of $5.00 USDT[/white]\n" +
                    f"[yellow]Your order value: {quantity} {symbol.replace('USDT', '')} × ${current_price:.4f} = ${order_value:.2f} USDT[/yellow]\n" +
                    f"[green]💡 Suggested minimum quantity: {min_qty:.6f} {symbol.replace('USDT', '')}[/green]",
                    title="⚠️ Minimum Trade Value Not Met",
                    border_style="red"
                ))
            elif "LOT_SIZE" in error_msg:
                # Get symbol info for lot size
                symbol_info = self.client.get_symbol_info(symbol)
                lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
                if lot_size_filter:
                    step_size = float(lot_size_filter['stepSize'])
                    valid_qty = self._adjust_to_step_size(quantity, step_size)
                    console.print(Panel(
                        f"[red]❌ Invalid quantity step size[/red]\n" +
                        f"[white]Quantity must be in increments of {step_size}[/white]\n" +
                        f"[yellow]Your quantity: {quantity}[/yellow]\n" +
                        f"[green]💡 Suggested valid quantity: {valid_qty}[/green]",
                        title="⚠️ Invalid Quantity",
                        border_style="yellow"
                    ))
                else:
                    console.print("[red]Error: Invalid lot size. Please adjust your quantity.[/red]")
            elif "PRICE_FILTER" in error_msg:
                console.print("[red]Error: Invalid price. Please adjust your price.[/red]")
            else:
                console.print(f"[red]Binance API Error: {error_msg}[/red]")
            logger.error(f"Error placing order: {e}")
            log_error(f"Failed to place {order_type} order for {symbol}: {str(e)}")
        except Exception as e:
            console.print(f"[red]Unexpected error: {str(e)}[/red]")
            logger.error(f"Error placing order: {e}")
            log_error(f"Failed to place {order_type} order for {symbol}: {str(e)}")
        return None

    def _is_valid_step_size(self, quantity, step_size):
        """Check if quantity follows the step size rules"""
        precision = len(str(step_size).split('.')[-1])
        return round(quantity % step_size, precision) == 0

    def _adjust_to_step_size(self, quantity, step_size):
        """Adjust quantity to valid step size"""
        return round(quantity - (quantity % step_size), 8)

    def process_order_update(self, msg):
        try:
            if msg.get('e') == 'executionReport':
                order_status = msg.get('X')
                symbol = msg.get('s')
                order_id = msg.get('i')
                order_type = msg.get('o')
                side = msg.get('S')
                price = msg.get('p')
                executed_qty = msg.get('z')
                executed_price = msg.get('L')  # Last executed price
                timestamp = datetime.fromtimestamp(msg.get('T') / 1000)

                status_colors = {
                    'NEW': 'blue',
                    'PARTIALLY_FILLED': 'yellow',
                    'FILLED': 'green',
                    'CANCELED': 'red',
                    'REJECTED': 'red',
                    'EXPIRED': 'red'
                }

                table = Table(title=f"Real-time Order Update - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style=status_colors.get(order_status, 'white'))
                
                table.add_row("Order ID", str(order_id))
                table.add_row("Symbol", symbol)
                table.add_row("Type", order_type)
                table.add_row("Side", side)
                table.add_row("Status", order_status)
                table.add_row("Price", price)
                table.add_row("Executed Qty", executed_qty)
                if executed_price:
                    table.add_row("Last Executed Price", executed_price)
                
                console.print(table)
                logger.info(f"Real-time update for Order {order_id}: {order_status}")
        except Exception as e:
            logger.error(f"Error processing order update: {e}")

    def twap(self, symbol, side, total_qty, interval_sec, slices):
        try:
            qty_per_order = round(total_qty / slices, 6)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
            ) as progress:
                
                task = progress.add_task(f"[cyan]Running TWAP: {slices} slices", total=slices)
                
                for i in range(slices):
                    progress.update(task, description=f"[cyan]Executing slice {i+1}/{slices}")
                    if not self.place_order(symbol, side, 'MARKET', qty_per_order):
                        raise Exception(f"Failed to place order for slice {i+1}")
                    time.sleep(interval_sec)
                    progress.advance(task)
                
                console.print("[green]TWAP execution completed successfully[/green]")
                
        except Exception as e:
            console.print(f"[red]TWAP execution failed: {str(e)}[/red]")

    def grid(self, symbol, lower_price, upper_price, grids, quantity, side):
        try:
            # Get current price
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Validate grid parameters
            if lower_price >= upper_price:
                console.print("[red]Error: Lower price must be less than upper price[/red]")
                return
            
            # Calculate price deviation percentage
            lower_deviation = abs(lower_price - current_price) / current_price
            upper_deviation = abs(upper_price - current_price) / current_price
            
            # Show warning if price range is too wide (e.g., more than 50% from current price)
            if lower_deviation > 0.5 or upper_deviation > 0.5:
                console.print(Panel(
                    f"[yellow]Warning: Grid price range is significantly deviated from current market price[/yellow]\n" +
                    f"[white]Current price: ${current_price:.8f}[/white]\n" +
                    f"[white]Lower price deviation: {lower_deviation*100:.1f}%[/white]\n" +
                    f"[white]Upper price deviation: {upper_deviation*100:.1f}%[/white]\n" +
                    f"[green]Recommended range:[/green]\n" +
                    f"[green]Lower: ${current_price * 0.5:.8f} to ${current_price * 0.9:.8f}[/green]\n" +
                    f"[green]Upper: ${current_price * 1.1:.8f} to ${current_price * 1.5:.8f}[/green]",
                    title="Grid Price Range Warning",
                    border_style="yellow"
                ))
                if not Confirm.ask("Do you want to continue with these prices?"):
                    return
            
            # Calculate grid parameters
            price_step = (upper_price - lower_price) / (grids - 1)
            
            # Show grid preview
            table = Table(title="Grid Trading Setup Preview")
            table.add_column("Level", style="cyan", justify="right")
            table.add_column("Price", style="green")
            table.add_column("Type", style="magenta")
            table.add_column("Quantity", style="blue")
            
            for i in range(grids):
                price = round(lower_price + i * price_step, 8)
                order_type = "BUY" if side == "BUY" else "SELL"
                table.add_row(
                    f"#{i+1}",
                    f"${price:.8f}",
                    order_type,
                    str(quantity)
                )
            
            console.print(table)
            
            if not Confirm.ask("\nDo you want to place these grid orders?"):
                return
            
            # Place grid orders
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%")
            ) as progress:
                
                task = progress.add_task("[cyan]Setting up grid orders", total=grids)
                
                for i in range(grids):
                    price = round(lower_price + i * price_step, 8)
                    if not self.place_order(symbol, side, 'LIMIT', quantity, price):
                        console.print(f"[red]Failed to place grid order {i+1}[/red]")
                        if not Confirm.ask("Do you want to continue placing remaining orders?"):
                            break
                    progress.advance(task)
                
            console.print("[green]Grid setup completed[/green]")
                
        except Exception as e:
            console.print(f"[red]Error setting up grid: {str(e)}[/red]")

    def get_account_info(self):
        try:
            params = {
                'timestamp': int(time.time() * 1000),
                'recvWindow': 5000
            }
            account_info = self.client.get_account(**params)
            
            # Filter balances to show only coins with non-zero balance
            non_zero_balances = [{
                'asset': balance['asset'],
                'free': float(balance['free']),
                'locked': float(balance['locked'])
            } for balance in account_info['balances']
                if float(balance['free']) > 0 or float(balance['locked']) > 0]
            
            if non_zero_balances:
                # Create and style the table
                table = Table(title="Account Balances", show_header=True, header_style="bold magenta")
                table.add_column("Asset", style="cyan")
                table.add_column("Available", style="green")
                table.add_column("Locked", style="yellow")
                
                for balance in non_zero_balances:
                    table.add_row(
                        balance['asset'],
                        f"{balance['free']:.8f}",
                        f"{balance['locked']:.8f}"
                    )
                
                console.print(table)
            else:
                console.print("[yellow]No coins with non-zero balance found.[/yellow]")
                
        except BinanceAPIException as e:
            console.print(f"[red]Failed to fetch account info: {str(e)}[/red]")

    def validate_symbol(self, symbol):
        try:
            # Get symbol info from Binance API
            symbol_info = self.client.get_symbol_info(symbol)
            
            if not symbol_info:
                raise ValueError(f"Trading pair {symbol} not found")
            
            if not symbol_info.get('isSpotTradingAllowed'):
                raise ValueError(f"Spot trading is not allowed for {symbol}")
            
            # Find the LOT_SIZE filter
            lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            # Find the PRICE_FILTER
            price_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER'), None)
            
            # Create info table
            table = Table(title=f"Symbol Information - {symbol}", show_header=True)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            # Add relevant trading info
            table.add_row("Base Asset", symbol_info['baseAsset'])
            table.add_row("Quote Asset", symbol_info['quoteAsset'])
            
            if lot_size_filter:
                table.add_row("Min Quantity", lot_size_filter['minQty'])
                table.add_row("Max Quantity", lot_size_filter['maxQty'])
                table.add_row("Step Size", lot_size_filter['stepSize'])
            
            if price_filter:
                table.add_row("Tick Size", price_filter['tickSize'])
            
            console.print(table)
            return symbol_info
            
        except BinanceAPIException as e:
            logger.error(f"Failed to validate symbol {symbol}: {e}")
            raise ValueError(f"Failed to validate symbol {symbol}: {e}")

    def verify_spot_access(self):
        try:
            # Try to get account information to verify API access
            account_info = self.client.get_account()
            # Verify trading is enabled
            if account_info.get('canTrade'):
                logger.info("Successfully verified spot trading access")
                return True
            else:
                logger.error("Spot trading is not enabled for this account")
                raise BinanceAPIException("Spot trading not enabled")
        except BinanceAPIException as e:
            logger.error(f"Failed to verify spot trading access: {e}")
            raise e

def main():
    console.print(Panel.fit(
        "[bold blue]Binance Trading Bot[/bold blue]\n" +
        "[dim]Testnet Edition[/dim]",
        border_style="blue"
    ))
    
    console.print("[bold blue]Initializing bot...[/bold blue]")
    bot = BasicBot(API_KEY, API_SECRET)
    
    while True:
        # Create mode selection table
        table = Table(title="Available Options", show_header=True, header_style="bold magenta")
        table.add_column("Mode", style="cyan")
        table.add_column("Description", style="green")
        table.add_row("MARKET", "Instant execution at market price")
        table.add_row("LIMIT", "Place order at specific price")
        table.add_row("STOP_MARKET", "Market order triggered at stop price")
        table.add_row("TWAP", "Time-Weighted Average Price execution")
        table.add_row("GRID", "Grid trading strategy")
        table.add_row("ACCOUNT", "View account balances")
        table.add_row("EXIT", "Exit the program")
        console.print(table)
        
        mode = Prompt.ask(
            "Choose mode",
            choices=["MARKET", "LIMIT", "STOP_MARKET", "TWAP", "GRID", "ACCOUNT", "EXIT"]
        )
        
        if mode == "EXIT":
            console.print("[bold blue]Shutting down bot...[/bold blue]")
            bot.twm.stop()  # Clean up WebSocket connection
            console.print("[bold blue]Thank you for using Binance Trading Bot![/bold blue]")
            break
        
        if mode == "ACCOUNT":
            bot.get_account_info()
            continue
        
        # Symbol selection with validation
        symbol = Prompt.ask("Symbol", default=DEFAULT_SYMBOL)
        try:
            symbol_info = bot.validate_symbol(symbol)
            console.print(f"[green]Trading pair {symbol} validated successfully[/green]")
        except (BinanceAPIException, ValueError) as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            continue

        if mode in ['MARKET', 'LIMIT', 'STOP_MARKET']:
            side = Prompt.ask("Side", choices=["BUY", "SELL"])
            qty = get_float("Quantity")
            price = stop_price = None
            
            if mode == 'LIMIT':
                price = get_float("Limit Price")
            elif mode == 'STOP_MARKET':
                stop_price = get_float("Stop Price")
                
            bot.place_order(symbol, side, mode, qty, price, stop_price)

        elif mode == 'TWAP':
            side = Prompt.ask("Side", choices=["BUY", "SELL"])
            total_qty = get_float("Total Quantity")
            slices = int(get_float("Number of Slices"))
            interval = get_float("Interval (seconds)")
            bot.twap(symbol, side, total_qty, interval, slices)

        elif mode == 'GRID':
            side = Prompt.ask("Base side for grid", choices=["BUY", "SELL"])
            lower = get_float("Lower Price")
            upper = get_float("Upper Price")
            grids = int(get_float("Number of Grid Levels"))
            qty = get_float("Quantity per order")
            bot.grid(symbol, lower, upper, grids, qty, side)

        if not Confirm.ask("\nWould you like to perform another action?"):
            console.print("[bold blue]Thank you for using Binance Trading Bot![/bold blue]")
            break

def get_float(prompt):
    while True:
        try:
            value = float(Prompt.ask(prompt))
            if value <= 0:
                console.print("[red]Value must be greater than 0[/red]")
                continue
            return value
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")

if __name__ == "__main__":
    main()
