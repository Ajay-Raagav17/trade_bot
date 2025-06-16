from fastapi import APIRouter, Depends, HTTPException, status, Response, Path as FastApiPath
from sqlalchemy.orm import Session
from typing import List as PyList
import uuid
import logging
import asyncio

from trading_bot_backend.database import get_db
from trading_bot_backend.services import user_api_key_service
from trading_bot_backend.schemas import user_api_key_schemas as schemas
from trading_bot_backend.auth import get_current_user_id
from trading_bot_backend.utils.encryption import decrypt_value # For constructing response model with preview

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users/api-keys",
    tags=["User API Keys Management"],  # Standardized tag
    # Common responses for this router
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized - Invalid or missing JWT."},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden - User does not have permission or API key is invalid/not found for user."},
        status.HTTP_404_NOT_FOUND: {"description": "Not found - The specified API key was not found for this user."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error - An unexpected error occurred on the server."},
    },
)

def _get_user_uuid(user_id_str: str) -> uuid.UUID:
    """Helper to convert user_id string from token to UUID, raising HTTPException if invalid."""
    try:
        return uuid.UUID(user_id_str)
    except ValueError:
        logger.warning(f"Invalid user ID format received from token: '{user_id_str}'")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format in token.")


@router.post(
    "",
    response_model=schemas.UserAPIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add New Binance API Key",
    description="Allows an authenticated user to add a new Binance API key and secret. The API key and secret are encrypted before storage. The full secret is never returned; only a preview of the API key is available in responses."
)
async def add_user_api_key(
    key_data: schemas.UserAPIKeyCreate,
    current_user_id_str: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_id = _get_user_uuid(current_user_id_str)
    # Optional: Add logic to limit the number of API keys per user here
    # e.g., by calling a count service method and checking against a constant.
    try:
        db_api_key = await asyncio.to_thread(user_api_key_service.create_user_api_key, db=db, user_id=user_id, key_data=key_data)

        decrypted_api_key_for_preview = await asyncio.to_thread(decrypt_value, db_api_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(decrypted_api_key_for_preview)

        return schemas.UserAPIKeyResponse(
            id=db_api_key.id, user_id=db_api_key.user_id, label=db_api_key.label,
            is_active=db_api_key.is_active, binance_api_key_preview=preview,
            is_valid_on_binance=db_api_key.is_valid_on_binance,
            last_validated_at=db_api_key.last_validated_at,
            created_at=db_api_key.created_at, updated_at=db_api_key.updated_at
        )
    except ValueError as ve: # Catch specific errors like encryption failure or DB commit issues from service
        logger.error(f"Value error while adding API key for user {user_id}: {ve}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e: # Catch any other unexpected server errors
        logger.error(f"Unexpected error adding API key for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while adding the API key.")


@router.get(
    "",
    response_model=PyList[schemas.UserAPIKeyResponse],
    summary="List User's API Keys",
    description="Retrieves a list of all API keys configured by the authenticated user. API secrets are never returned, and API keys are shown as masked previews."
)
async def read_user_api_keys(
    current_user_id_str: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_id = _get_user_uuid(current_user_id_str)
    db_keys = await asyncio.to_thread(user_api_key_service.get_user_api_keys, db=db, user_id=user_id)
    response_keys = []
    for db_key in db_keys:
        try:
            decrypted_api_key = await asyncio.to_thread(decrypt_value, db_key.binance_api_key_encrypted)
            preview = user_api_key_service.get_api_key_preview(decrypted_api_key)
        except Exception:
            preview = "Error: Key preview unavailable" # Provide a user-friendly error for preview
            logger.warning(f"Could not generate preview for key_id {db_key.id} (user {user_id}) due to decryption or processing error.")

        response_keys.append(schemas.UserAPIKeyResponse(
            id=db_key.id, user_id=db_key.user_id, label=db_key.label,
            is_active=db_key.is_active, binance_api_key_preview=preview,
            is_valid_on_binance=db_key.is_valid_on_binance,
            last_validated_at=db_key.last_validated_at,
            created_at=db_key.created_at, updated_at=db_key.updated_at
        ))
    return response_keys


@router.put(
    "/{key_id}",
    response_model=schemas.UserAPIKeyResponse,
    summary="Update API Key Label or Status",
    description="Allows updating the user-defined label or the active status of a specific API key. The API key and secret themselves cannot be modified via this endpoint."
)
async def update_user_api_key_endpoint(
    key_id: int = FastApiPath(..., description="The internal database ID of the API key to update."),
    key_update_data: schemas.UserAPIKeyUpdate,
    current_user_id_str: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_id = _get_user_uuid(current_user_id_str)
    updated_key = await asyncio.to_thread(user_api_key_service.update_user_api_key,
                                          db=db, user_id=user_id, key_id=key_id, key_update_data=key_update_data)
    if not updated_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found or you do not have permission to update it.")

    try:
        decrypted_api_key = await asyncio.to_thread(decrypt_value, updated_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(decrypted_api_key)
    except Exception:
        preview = "Error: Key preview unavailable"
        logger.warning(f"Could not generate preview for updated key_id {updated_key.id} (user {user_id}).")

    return schemas.UserAPIKeyResponse(
        id=updated_key.id, user_id=updated_key.user_id, label=updated_key.label,
        is_active=updated_key.is_active, binance_api_key_preview=preview,
        is_valid_on_binance=updated_key.is_valid_on_binance,
        last_validated_at=updated_key.last_validated_at,
        created_at=updated_key.created_at, updated_at=updated_key.updated_at
    )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API Key",
    description="Deletes a specific API key for the authenticated user. This operation is permanent and cannot be undone."
)
async def delete_user_api_key_endpoint(
    key_id: int = FastApiPath(..., description="The internal database ID of the API key to delete."),
    current_user_id_str: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_id = _get_user_uuid(current_user_id_str)
    success = await asyncio.to_thread(user_api_key_service.delete_user_api_key, db=db, user_id=user_id, key_id=key_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found or you do not have permission to delete it.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{key_id}/validate",
    response_model=schemas.UserAPIKeyResponse,
    summary="Validate API Key with Binance",
    description="Triggers a server-side test of the specified API key against the Binance API to check its validity and necessary permissions (e.g., ability to read account info, execute trades). This updates the key's validation status and last validated timestamp in the database."
)
async def validate_user_api_key_endpoint(
    key_id: int = FastApiPath(..., description="The internal database ID of the API key to validate."),
    current_user_id_str: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user_id = _get_user_uuid(current_user_id_str)
    try:
        # The service function test_and_update_api_key_status handles decryption and Binance client interaction
        await asyncio.to_thread(user_api_key_service.test_and_update_api_key_status,
                                db=db, user_id=user_id, key_id=key_id)
    except ValueError as ve: # Catch specific "not found" or "decryption" errors from service
         logger.warning(f"Validation process error for key_id {key_id}, user {user_id}: {ve}")
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e: # Catch other errors like BinanceAPIException if not handled in service, or unexpected
        logger.error(f"Validation task unexpectedly failed for key_id {key_id}, user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred during API key validation: {str(e)}")

    db_key = await asyncio.to_thread(user_api_key_service.get_user_api_key_by_id, db=db, user_id=user_id, key_id=key_id)
    if not db_key: # Should ideally be caught by test_and_update if key doesn't exist for user
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found after validation attempt.")

    try:
        decrypted_api_key = await asyncio.to_thread(decrypt_value, db_key.binance_api_key_encrypted)
        preview = user_api_key_service.get_api_key_preview(decrypted_api_key)
    except Exception:
        preview = "Error processing key preview"
        logger.warning(f"Could not generate preview for validated key_id {db_key.id} for user {user_id}")

    return schemas.UserAPIKeyResponse(
        id=db_key.id, user_id=db_key.user_id, label=db_key.label,
        is_active=db_key.is_active, binance_api_key_preview=preview,
        is_valid_on_binance=db_key.is_valid_on_binance,
        last_validated_at=db_key.last_validated_at,
        created_at=db_key.created_at, updated_at=db_key.updated_at
    )
```
