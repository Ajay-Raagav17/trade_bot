import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer # Expecting Bearer token
from jose import JWTError, jwt
from typing import Optional, Dict, Any, List # Added List for jwks["keys"] type hint
import logging
import os

logger = logging.getLogger(__name__)

# Configuration from env.py or environment variables
try:
    from trading_bot_backend.bot.env import (
        SUPABASE_JWKS_URI,
        SUPABASE_JWT_AUDIENCE,
        SUPABASE_JWT_ISSUER,
        SUPABASE_URL # Also import SUPABASE_URL if needed for fallback derivation
    )
except ImportError:
    logger.warning("Could not import Supabase JWT config from trading_bot_backend.bot.env. Using os.getenv.")
    SUPABASE_URL = os.getenv('SUPABASE_URL') # Keep SUPABASE_URL available
    SUPABASE_JWKS_URI = os.getenv('SUPABASE_JWKS_URI')
    if not SUPABASE_JWKS_URI and SUPABASE_URL and SUPABASE_URL.startswith('http') and 'your-project-ref' not in SUPABASE_URL:
        SUPABASE_JWKS_URI = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        logger.info(f"Derived SUPABASE_JWKS_URI from SUPABASE_URL: {SUPABASE_JWKS_URI}")

    SUPABASE_JWT_AUDIENCE = os.getenv('SUPABASE_JWT_AUDIENCE', 'authenticated')

    SUPABASE_JWT_ISSUER = os.getenv('SUPABASE_JWT_ISSUER')
    if not SUPABASE_JWT_ISSUER and SUPABASE_URL and SUPABASE_URL.startswith('http') and 'your-project-ref' not in SUPABASE_URL:
        SUPABASE_JWT_ISSUER = f"{SUPABASE_URL}/auth/v1"
        logger.info(f"Derived SUPABASE_JWT_ISSUER from SUPABASE_URL: {SUPABASE_JWT_ISSUER}")


if not all([SUPABASE_JWKS_URI, SUPABASE_JWT_AUDIENCE, SUPABASE_JWT_ISSUER]):
    logger.critical(
        "Supabase JWT configuration (JWKS_URI, AUDIENCE, ISSUER) is missing or incomplete. "
        "Authentication will likely fail. Ensure SUPABASE_URL is correctly set or provide these values directly."
    )
    # Consider raising an error here if critical settings are missing at startup
    # For example: raise RuntimeError("Critical Supabase JWT settings are missing.")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/dummy_token_url") # Changed dummy URL slightly

jwks_cache: Optional[Dict[str, Any]] = None
# TODO: Add a lock for jwks_cache update if using in a highly concurrent async environment,
# or use a more robust caching mechanism with TTL. For now, simple global cache.

async def fetch_jwks() -> Dict[str, Any]:
    global jwks_cache
    # Basic cache check (no TTL for this example, consider adding one for production)
    if jwks_cache:
        logger.debug("Using cached JWKS.")
        return jwks_cache

    if not SUPABASE_JWKS_URI:
        logger.error("SUPABASE_JWKS_URI is not configured. Cannot fetch JWKS.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system misconfiguration: JWKS URI is missing."
        )

    try:
        logger.info(f"Fetching JWKS from {SUPABASE_JWKS_URI}...")
        async with httpx.AsyncClient(timeout=10.0) as client: # Added timeout
            response = await client.get(SUPABASE_JWKS_URI)
            response.raise_for_status()
            new_jwks = response.json()
            if not isinstance(new_jwks, dict) or "keys" not in new_jwks or not isinstance(new_jwks["keys"], list):
                logger.error(f"Invalid JWKS format received from {SUPABASE_JWKS_URI}. Expected dict with 'keys' list.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid JWKS format received.")

            jwks_cache = new_jwks
            logger.info("JWKS fetched and cached successfully.")
            return new_jwks
    except httpx.TimeoutException:
        logger.error(f"Timeout while fetching JWKS from {SUPABASE_JWKS_URI}.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Timeout fetching authentication keys.")
    except httpx.RequestError as e:
        logger.error(f"HTTP error fetching JWKS from {SUPABASE_JWKS_URI}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not fetch authentication keys from provider.")
    except Exception as e:
        logger.error(f"Unexpected error processing JWKS response: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing authentication keys.")


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    # Centralized exception for auth failures
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Re-check critical config at request time in case env vars were loaded late or changed
    if not all([SUPABASE_JWKS_URI, SUPABASE_JWT_AUDIENCE, SUPABASE_JWT_ISSUER]):
        logger.critical("JWT Audience, Issuer, or JWKS URI not configured properly at time of request.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth system critical misconfiguration.")

    try:
        jwks = await fetch_jwks() # JWKS should have been fetched and cached by now or on first call

        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks.get("keys", []): # Ensure "keys" exists and is a list
            if key.get("kid") == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key.get("kty"), "kid": key.get("kid"),
                    "use": key.get("use"), "n": key.get("n"), "e": key.get("e")
                }
                break

        if not rsa_key:
            logger.warning(f"Public key not found in JWKS for kid: {unverified_header.get('kid')}. JWKS may be stale or token is invalid.")
            # Optionally, try to refresh JWKS cache once if key not found
            global jwks_cache; jwks_cache = None # Clear cache
            jwks = await fetch_jwks() # Retry fetch
            for key in jwks.get("keys", []):
                 if key.get("kid") == unverified_header.get("kid"): rsa_key = {...}; break # Simplified
            if not rsa_key: # If still not found after refresh
                 logger.error(f"Public key still not found in refreshed JWKS for kid: {unverified_header.get('kid')}.")
                 raise credentials_exception

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=SUPABASE_JWT_AUDIENCE,
            issuer=SUPABASE_JWT_ISSUER
        )

        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            logger.error("User ID (sub claim) not found in JWT payload.")
            raise credentials_exception

        # Additional checks (e.g., 'exp' is handled by jwt.decode)
        # Check 'role' or 'aal' if your app requires specific values
        # if payload.get('role') != 'authenticated': # Example check
        #     logger.warning(f"User {user_id} has role '{payload.get('role')}' not 'authenticated'.")
        #     raise credentials_exception

        logger.info(f"JWT validated successfully for user_id: {user_id}")
        return user_id

    except JWTError as e:
        logger.warning(f"JWT validation error: {e}", exc_info=True) # Log with stack for JWT specific errors
        raise credentials_exception
    except HTTPException as e: # Re-raise HTTPExceptions from fetch_jwks or our own
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}", exc_info=True)
        raise credentials_exception
