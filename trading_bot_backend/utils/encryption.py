from cryptography.fernet import Fernet
# No need for base64 import if key is already Fernet-generated (URL-safe base64)
import os
import logging

logger = logging.getLogger(__name__)

SECRET_ENCRYPTION_KEY_STR = None
try:
    # Attempt to import the key directly from env.py (if it's defined there)
    from trading_bot_backend.bot.env import SECRET_ENCRYPTION_KEY as ENV_KEY_VALUE
    SECRET_ENCRYPTION_KEY_STR = ENV_KEY_VALUE
    logger.info('SECRET_ENCRYPTION_KEY imported from env.py.')
except ImportError:
    logger.warning('Could not import SECRET_ENCRYPTION_KEY from env.py. Falling back to os.getenv.')
    SECRET_ENCRYPTION_KEY_STR = os.getenv('SECRET_ENCRYPTION_KEY')

fernet_instance = None
if not SECRET_ENCRYPTION_KEY_STR or 'your_strong_32_byte_fernet_key_here' in SECRET_ENCRYPTION_KEY_STR:
    logger.critical('CRITICAL: SECRET_ENCRYPTION_KEY is not configured or is using the placeholder value!')
    logger.warning('Encryption/decryption will NOT be available.')
else:
    try:
        # The key from env should be a URL-safe base64 encoded string (output of Fernet.generate_key())
        key_bytes_for_fernet = SECRET_ENCRYPTION_KEY_STR.encode('utf-8')
        fernet_instance = Fernet(key_bytes_for_fernet)
        logger.info('Fernet encryption service initialized successfully.')
    except Exception as e:
        logger.critical(f'CRITICAL: Failed to initialize Fernet with SECRET_ENCRYPTION_KEY. Error: {e}.')
        logger.warning('Ensure SECRET_ENCRYPTION_KEY is a valid URL-safe base64 encoded 32-byte key (output of Fernet.generate_key()).')

def generate_new_fernet_key() -> str:
    # This function should be called by an admin or during setup, not typically at runtime.
    key = Fernet.generate_key()
    # The f-string that caused issues with echo:
    logger.info(f"Generated new Fernet key (use this for SECRET_ENCRYPTION_KEY in your .env or env.py): {key.decode('utf-8')}")
    return key.decode('utf-8')

def encrypt_value(value: str) -> str:
    if not fernet_instance:
        logger.error('Encryption service not initialized. Cannot encrypt.')
        raise ValueError('Encryption service not available. SECRET_ENCRYPTION_KEY might be missing or invalid.')
    return fernet_instance.encrypt(value.encode('utf-8')).decode('utf-8')

def decrypt_value(encrypted_value: str) -> str:
    if not fernet_instance:
        logger.error('Decryption service not initialized. Cannot decrypt.')
        raise ValueError('Decryption service not available. SECRET_ENCRYPTION_KEY might be missing or invalid.')
    return fernet_instance.decrypt(encrypted_value.encode('utf-8')).decode('utf-8')

# Example of how to generate a key if needed (run this script directly or call this function from a setup script)
# if __name__ == '__main__':
#     print('Generating a new Fernet encryption key example:')
#     generate_new_fernet_key()
