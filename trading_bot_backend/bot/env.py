import os

# Binance API Credentials (original, to be stored securely via DB later)
# These are placeholders and should be replaced by actual keys or loaded from a secure environment.
API_KEY = os.getenv('BINANCE_API_KEY', "your_binance_api_key_here")
API_SECRET = os.getenv('BINANCE_API_SECRET', "your_binance_api_secret_here")

# Old Basic Authentication Credentials (will be superseded by JWT)
TRADING_BOT_USERNAME = os.getenv('TRADING_BOT_USERNAME', 'your_username_here')
TRADING_BOT_PASSWORD = os.getenv('TRADING_BOT_PASSWORD', 'your_password_here')

# --- Database Configuration ---
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@host:port/dbname')

# --- Encryption Key for API Secrets ---
# IMPORTANT: Generate a strong, random key (e.g., using Fernet.generate_key()) and keep it secret!
SECRET_ENCRYPTION_KEY = os.getenv('SECRET_ENCRYPTION_KEY', 'your_strong_32_byte_fernet_key_here')

# --- Supabase JWT Configuration ---
# These should be set in your environment for production.
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://your-project-ref.supabase.co')

# For RS256 (common with Supabase), we need the JWKS URI to fetch public keys.
# It's generally better to use the JWKS URI for key rotation handling.
# Example for SUPABASE_PUBLIC_KEY_PEM (alternative, if JWKS is not used):
# SUPABASE_PUBLIC_KEY_PEM = os.getenv('SUPABASE_PUBLIC_KEY_PEM', """-----BEGIN PUBLIC KEY-----
# MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyourkeydetails...
# -----END PUBLIC KEY-----""")

DEFAULT_JWKS_URI = ''
DEFAULT_JWT_ISSUER = ''

# Check if SUPABASE_URL is a valid-looking HTTP/HTTPS URL and not the placeholder
if SUPABASE_URL and SUPABASE_URL.startswith(('http://', 'https://')) and 'your-project-ref' not in SUPABASE_URL:
    DEFAULT_JWKS_URI = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    DEFAULT_JWT_ISSUER = f"{SUPABASE_URL}/auth/v1"
else:
    if 'your-project-ref' in SUPABASE_URL: # Log if it's the placeholder
        print(f"WARNING: env.py: SUPABASE_URL is set to the placeholder value '{SUPABASE_URL}'. Real-time derivation of JWKS URI and Issuer will be skipped.")
    elif not SUPABASE_URL.startswith(('http://', 'https://')):
        print(f"WARNING: env.py: SUPABASE_URL '{SUPABASE_URL}' does not look like a valid URL. Real-time derivation of JWKS URI and Issuer will be skipped.")


SUPABASE_JWKS_URI = os.getenv('SUPABASE_JWKS_URI', DEFAULT_JWKS_URI)
SUPABASE_JWT_AUDIENCE = os.getenv('SUPABASE_JWT_AUDIENCE', 'authenticated') # Often 'authenticated' for Supabase
SUPABASE_JWT_ISSUER = os.getenv('SUPABASE_JWT_ISSUER', DEFAULT_JWT_ISSUER)

# Ensure critical JWT settings have some value, even if it's the default derived one or an empty string.
# The auth logic will need to handle cases where these might be empty if not properly configured.
if not SUPABASE_JWKS_URI and not os.getenv('SUPABASE_PUBLIC_KEY_PEM'): # If neither JWKS nor static key is likely configured
    print("WARNING: env.py: SUPABASE_JWKS_URI is not set and no SUPABASE_PUBLIC_KEY_PEM seems configured. JWT validation will likely fail.")

if not SUPABASE_JWT_ISSUER:
    print("WARNING: env.py: SUPABASE_JWT_ISSUER could not be derived or set. JWT validation might fail.")

```
