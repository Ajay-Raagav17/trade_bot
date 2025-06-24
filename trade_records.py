import logging

# Configure logger to append to bot.log
# This will use the same logger instance as in codebase.py if it's already configured.
# If not, it will create a basic configuration.
logger = logging.getLogger("trading_bot")

# Ensure the logger has handlers, otherwise it might not output if this module is imported before codebase.py configures it.
if not logger.handlers:
    # Basic configuration if not already set up by codebase.py
    # This is a fallback and ideally codebase.py's RichHandler setup should be the primary one.
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                        handlers=[logging.FileHandler("bot.log", mode='a')])

def log_order(order_type, symbol, side, quantity, price=None, status=None, order_id=None):
    """
    Logs order details.
    Can be called before placing an order (status and order_id will be None)
    or after an order attempt (status and order_id might be populated).
    """
    log_message_parts = [
        f"Order Log: Type={order_type}",
        f"Symbol={symbol}",
        f"Side={side}",
        f"Quantity={quantity}"
    ]
    if price is not None:
        log_message_parts.append(f"Price={price}")
    if status is not None:
        log_message_parts.append(f"Status={status}")
    if order_id is not None:
        log_message_parts.append(f"OrderID={order_id}")

    log_message = ", ".join(log_message_parts)
    logger.info(log_message)

def log_error(error_message):
    """
    Logs an error message.
    """
    logger.error(f"Error Log: {error_message}")

if __name__ == '__main__':
    # Example usage for testing this module directly
    # This part will only run if trade_records.py is executed as the main script
    print("Testing trade_records.py logging...")

    # Configure a simple console handler for direct testing if no handlers are present
    if not logger.handlers or all(isinstance(h, logging.FileHandler) for h in logger.handlers):
        # Add console handler if only file handler is present or no handlers
        # This avoids duplicate console output if RichHandler is already set by codebase.py
        # For direct script run, we want to see output on console.
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        # Remove existing file handlers for direct test to avoid writing to file from here
        # logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.FileHandler)]
        logger.addHandler(ch)
        logger.propagate = False # Avoid passing to root logger if we added a handler

    logger.info("This is an info test from trade_records.py direct execution.")
    log_order("MARKET", "BTCUSDT", "BUY", 0.001)
    log_order("LIMIT", "ETHUSDT", "SELL", 0.1, price=2000.0, status="NEW", order_id="12345")
    log_error("This is a test error message from trade_records.py.")
    print(f"Test logs should be in bot.log and possibly on console if run directly.")
    print(f"Logger handlers: {logger.handlers}")
    print(f"Logger effective level: {logger.getEffectiveLevel()}")
    print(f"Logger propagate: {logger.propagate}")
