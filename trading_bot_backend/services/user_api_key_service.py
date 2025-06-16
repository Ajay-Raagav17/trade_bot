from sqlalchemy.orm import Session
from sqlalchemy import desc # For ordering by updated_at
from typing import List, Optional
from datetime import datetime, timezone # Ensure timezone for utcnow
import uuid
import logging

from trading_bot_backend import models # SQLAlchemy models (imports models.UserAPIKeys)
from trading_bot_backend.schemas import user_api_key_schemas as schemas # Pydantic schemas
from trading_bot_backend.utils.encryption import encrypt_value, decrypt_value # Encryption utilities
from binance.client import Client # To test API keys
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

def create_user_api_key(db: Session, user_id: uuid.UUID, key_data: schemas.UserAPIKeyCreate) -> models.UserAPIKeys:
    """
    Creates a new API key record for a user, encrypting the key and secret.
    """
    logger.info(f"Attempting to create API Key for user {user_id}, label: {key_data.label}")
    try:
        encrypted_api_key = encrypt_value(key_data.binance_api_key)
        encrypted_api_secret = encrypt_value(key_data.binance_api_secret)
    except ValueError as e_encrypt: # Catch errors from encryption service (e.g., if not initialized)
        logger.error(f"Encryption failed for user {user_id}: {e_encrypt}", exc_info=True)
        raise ValueError(f"Could not create API key due to encryption error: {e_encrypt}")


    # Preview: first 5 and last 5 characters
    # This preview is not stored in DB, but UserAPIKeyResponse schema needs it.
    # It will be generated on-the-fly when converting model to schema.

    db_api_key = models.UserAPIKeys(
        user_id=user_id,
        label=key_data.label,
        binance_api_key_encrypted=encrypted_api_key,
        binance_api_secret_encrypted=encrypted_api_secret,
        is_active=key_data.is_active,
        is_valid_on_binance=False, # Initial state, validation is a separate step
        last_validated_at=None
    )
    db.add(db_api_key)
    try:
        db.commit()
        db.refresh(db_api_key)
        logger.info(f"API Key record created with ID {db_api_key.id} for user {user_id}.")
        return db_api_key
    except Exception as e_commit:
        db.rollback()
        logger.error(f"Database commit failed while creating API key for user {user_id}: {e_commit}", exc_info=True)
        raise ValueError(f"Could not save API key to database: {e_commit}")


def get_user_api_keys(db: Session, user_id: uuid.UUID) -> List[models.UserAPIKeys]:
    """
    Retrieves all API key records for a specific user.
    """
    logger.debug(f"Fetching all API keys for user {user_id}")
    return db.query(models.UserAPIKeys).filter(models.UserAPIKeys.user_id == user_id).order_by(desc(models.UserAPIKeys.created_at)).all()

def get_user_api_key_by_id(db: Session, user_id: uuid.UUID, key_id: int) -> Optional[models.UserAPIKeys]:
    """
    Retrieves a specific API key record by its ID, ensuring it belongs to the user.
    """
    logger.debug(f"Fetching API key ID {key_id} for user {user_id}")
    return db.query(models.UserAPIKeys).filter(
        models.UserAPIKeys.id == key_id,
        models.UserAPIKeys.user_id == user_id
    ).first()

def get_active_valid_api_key_for_user(db: Session, user_id: uuid.UUID) -> Optional[models.UserAPIKeys]:
    """
    Retrieves the most recently updated, active, and validated API key for a user.
    This is typically used to get THE key for trading operations or WebSocket stream.
    """
    logger.debug(f"Fetching active and valid API key for user {user_id}")
    return db.query(models.UserAPIKeys).filter(
        models.UserAPIKeys.user_id == user_id,
        models.UserAPIKeys.is_active == True,
        models.UserAPIKeys.is_valid_on_binance == True
    ).order_by(models.UserAPIKeys.updated_at.desc()).first()


def get_decrypted_api_key(db_key: models.UserAPIKeys) -> str:
    """Helper to decrypt API key. Assumes db_key is a valid UserAPIKeys object."""
    try:
        return decrypt_value(db_key.binance_api_key_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt API key for key ID {db_key.id}: {e}", exc_info=True)
        raise ValueError(f"API Key decryption error for key ID {db_key.id}.")

def get_decrypted_api_secret(db_key: models.UserAPIKeys) -> str:
    """Helper to decrypt API secret. Assumes db_key is a valid UserAPIKeys object."""
    try:
        return decrypt_value(db_key.binance_api_secret_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt API secret for key ID {db_key.id}: {e}", exc_info=True)
        raise ValueError(f"API Secret decryption error for key ID {db_key.id}.")


def update_user_api_key(db: Session, user_id: uuid.UUID, key_id: int, key_update_data: schemas.UserAPIKeyUpdate) -> Optional[models.UserAPIKeys]:
    """
    Updates an existing API key record (label, is_active).
    Does NOT update the key/secret itself.
    """
    db_key = get_user_api_key_by_id(db, user_id=user_id, key_id=key_id)
    if not db_key:
        logger.warning(f"Update failed: API Key ID {key_id} not found for user {user_id}.")
        return None

    update_data = key_update_data.model_dump(exclude_unset=True)
    changed_fields = False
    for field, value in update_data.items():
        if getattr(db_key, field) != value:
            setattr(db_key, field, value)
            changed_fields = True

    if changed_fields:
        # If is_active is changed from False to True, should reset is_valid_on_binance
        if 'is_active' in update_data and update_data['is_active'] == True and db_key.is_valid_on_binance == False:
            logger.info(f"API Key ID {key_id} for user {user_id} re-activated. Validation status remains False until re-tested.")
            # Or, could trigger a re-validation here if desired, but that's an external call.
            # For now, just update. User should be prompted to re-validate if needed.

        db_key.updated_at = datetime.now(timezone.utc) # Manually set update timestamp
        try:
            db.commit()
            db.refresh(db_key)
            logger.info(f"API Key ID {key_id} for user {user_id} updated successfully.")
            return db_key
        except Exception as e_commit:
            db.rollback()
            logger.error(f"Database commit failed while updating API key ID {key_id} for user {user_id}: {e_commit}", exc_info=True)
            raise ValueError(f"Could not update API key in database: {e_commit}")
    else:
        logger.info(f"No changes detected for API Key ID {key_id}, user {user_id}. Update not committed.")
        return db_key


def delete_user_api_key(db: Session, user_id: uuid.UUID, key_id: int) -> bool:
    """
    Deletes an API key record for a user.
    """
    db_key = get_user_api_key_by_id(db, user_id=user_id, key_id=key_id)
    if not db_key:
        logger.warning(f"Delete failed: API Key ID {key_id} not found for user {user_id}.")
        return False

    try:
        db.delete(db_key)
        db.commit()
        logger.info(f"API Key ID {key_id} for user {user_id} deleted successfully.")
        return True
    except Exception as e_commit:
        db.rollback()
        logger.error(f"Database commit failed while deleting API key ID {key_id} for user {user_id}: {e_commit}", exc_info=True)
        raise ValueError(f"Could not delete API key from database: {e_commit}")


def test_and_update_api_key_status(db: Session, user_id: uuid.UUID, key_id: int) -> bool:
    """
    Tests the stored (decrypted) API key with Binance and updates its validation status.
    Returns True if valid, False otherwise.
    """
    db_key = get_user_api_key_by_id(db, user_id=user_id, key_id=key_id)
    if not db_key:
        logger.error(f"Cannot validate: API Key ID {key_id} not found for user {user_id}.")
        # Or raise an exception: raise ValueError(f"API Key ID {key_id} not found for user {user_id}")
        return False

    is_currently_valid_in_db = db_key.is_valid_on_binance

    validation_passed = False
    try:
        api_key = decrypt_value(db_key.binance_api_key_encrypted)
        api_secret = decrypt_value(db_key.binance_api_secret_encrypted)

        # Initialize a temporary Binance client with these keys
        # Ensure testnet=True if these are testnet keys. Bot currently defaults to testnet.
        client = Client(api_key, api_secret, testnet=True)
        client.get_account() # This API call will raise BinanceAPIException if keys are invalid or permissions are wrong
        validation_passed = True
        logger.info(f"API Key ID {key_id} for user {user_id} successfully validated with Binance.")
    except BinanceAPIException as e:
        logger.warning(f"Binance API validation failed for key ID {key_id}, user {user_id}: {e.code} - {e.message}")
        validation_passed = False
    except ValueError as e_decrypt: # Catch decryption errors
        logger.error(f"Decryption error during API key validation for key ID {key_id}, user {user_id}: {e_decrypt}", exc_info=True)
        validation_passed = False
    except Exception as e_unknown: # Catch other unexpected issues like network problems
        logger.error(f"Unexpected error during API key validation process for key ID {key_id}, user {user_id}: {e_unknown}", exc_info=True)
        validation_passed = False

    # Update database only if status changed or if it was never validated before
    if db_key.is_valid_on_binance != validation_passed or db_key.last_validated_at is None:
        db_key.is_valid_on_binance = validation_passed
        db_key.last_validated_at = datetime.now(timezone.utc)
        try:
            db.commit()
            db.refresh(db_key)
            logger.info(f"Updated validation status for API Key ID {key_id} to {validation_passed}.")
        except Exception as e_commit:
            db.rollback()
            logger.error(f"Database commit failed while updating validation status for API key ID {key_id}: {e_commit}", exc_info=True)
            # Return the live validation_passed status even if DB commit fails, client can know the live status
    else:
        logger.info(f"Validation status for API Key ID {key_id} remains {validation_passed}. No DB update needed.")

    return validation_passed

def get_api_key_preview(api_key_value: str) -> str:
    """Generates a preview string for an API key (e.g., first 5 and last 5 chars)."""
    if not isinstance(api_key_value, str) or len(api_key_value) < 10:
        return "Key Invalid"
    return f"{api_key_value[:5]}...{api_key_value[-5:]}"

```
