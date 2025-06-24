# Binance Trading Bot (Testnet Edition)

A Python-based trading bot for Binance that provides various trading functionalities through an interactive command-line interface. This bot runs on Binance's testnet, making it safe for learning and testing trading strategies without risking real money.

## Features

- **Multiple Order Types:**
  - Market Orders: Instant execution at current market price
  - Limit Orders: Place orders at specific price levels
  - Stop Market Orders: Automated market orders triggered at specified price levels

- **Advanced Trading Strategies:**
  - TWAP (Time-Weighted Average Price): Split large orders into smaller ones over time
  - Grid Trading: Automated buying and selling at predefined price intervals

- **Account Management:**
  - Real-time account balance viewing
  - Order tracking and history
  - Trade logging system

- **User Interface:**
  - Rich CLI interface with colored output
  - Interactive prompts for trade parameters
  - Clear error messages and validation
  - Real-time order status updates

## Prerequisites

- Python 3.8 or higher
- Binance Testnet Account
- API Key and Secret from Binance Testnet

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd binance-trading-bot
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Set up your API credentials:
   - Create a file named `env.py` with your Binance Testnet API credentials:
```python
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
```
Now already created and attached in env file
## Usage

1. Start the bot:
```bash
python codebase.py
```

2. Choose from available trading modes:
   - MARKET: For immediate execution
   - LIMIT: Set buy/sell orders at specific prices
   - STOP_MARKET: Set trigger prices for market orders
   - TWAP: Execute large orders over time
   - GRID: Set up grid trading strategy
   - ACCOUNT: View your account balances
   - EXIT: Close the program

   **Note on Input:** Mode selection is case-insensitive (e.g., 'market' or 'MARKET' will work). For symbol inputs, common coin tickers (like 'BTC', 'ETH', 'XRP') are automatically interpreted as their primary USDT pairs (e.g., 'BTCUSDT', 'ETHUSDT', 'XRPUSDT'). The bot will confirm the interpreted symbol before proceeding.

3. Follow the interactive prompts to:
   - Select trading pairs (you can use full names like 'BTCUSDT' or shorthands like 'BTC')
   - Enter order quantities
   - Set prices (for limit orders)
   - Configure strategy parameters

## Trading Modes Explained

### Market Order
- Instant execution at the current market price
- Best for immediate trades
- No price guarantee

### Limit Order
- Set your desired price
- Order executes only when market reaches your price
- Better price control but no guarantee of execution

### Stop Market
- Set a trigger price
- Market order executes when trigger price is reached
- Useful for stop-loss or take-profit strategies

### TWAP (Time-Weighted Average Price)
- Splits large orders into smaller pieces
- Executes over a specified time period
- Helps minimize market impact

### Grid Trading
- Creates a grid of buy and sell orders
- Automatically trades within price ranges
- Profits from price oscillations

## Safety Features

- Testnet Environment: No real money at risk
- Input Validation: Prevents invalid orders
- Minimum Order Checks: Ensures orders meet exchange requirements
- Error Handling: Clear error messages for common issues

## Logging

The bot maintains logs of all trading activities:
- Order details
- Execution status
- Error messages
- Trade history

Logs are stored in `bot.log`

## Error Handling

The bot includes comprehensive error handling for:
- Invalid inputs
- Network issues
- API errors
- Exchange-specific restrictions

## Disclaimer

This is a testing tool using Binance's testnet.



## License

[MIT License](LICENSE)
