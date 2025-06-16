from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
import uuid

class UserAPIKeyBase(BaseModel):
    label: Optional[str] = Field(
        None,
        description="A user-defined label for easy identification of the API key.",
        example="My Primary Binance Key",
        max_length=255
    )
    is_active: bool = Field(
        True,
        description="Set to false to temporarily disable this key for trading and data streaming without deleting it."
    )

class UserAPIKeyCreate(UserAPIKeyBase):
    binance_api_key: str = Field(
        ...,
        description="Your Binance API key. Ensure it has the necessary permissions (e.g., Spot & Margin Trading, Read Info).",
        min_length=64, # Standard Binance API Key length
        max_length=64,
        example="vmPUZE6mv9SD5VNHk4HlWFsOr6aKE2zvsw0MuIgwCIPy6utIco14y7Ju91duEh8A"
    )
    binance_api_secret: str = Field(
        ...,
        description="Your Binance API secret. This will be encrypted upon storage and is not retrievable.",
        min_length=64, # Standard Binance API Secret length
        max_length=64,
        example="NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvAQMwrffDEFgmcW"
    )

class UserAPIKeyUpdate(BaseModel):
    label: Optional[str] = Field(
        None,
        description="New label for the API key. Only provide if you want to change it.",
        example="Primary Spot Trading Key",
        max_length=255
    )
    is_active: Optional[bool] = Field(
        None,
        description="New active status for the API key. Set to 'true' to activate, 'false' to deactivate. Only provide if you want to change it."
    )
    # Note: Actual key/secret values cannot be updated. To change credentials, delete this entry and create a new one.

class UserAPIKeyResponse(UserAPIKeyBase):
    id: int = Field(..., description="Internal database ID of the API key record.")
    user_id: uuid.UUID = Field(..., description="The user ID (Supabase UUID) who owns this API key.")
    binance_api_key_preview: str = Field(
        ...,
        description="A masked preview of the API key (e.g., first 5 and last 4 characters) for identification purposes. The full key is never returned.",
        example="vmPUZ...Eh8A"
    )
    is_valid_on_binance: bool = Field(
        ...,
        description="Indicates if the key was successfully validated against Binance for required permissions (e.g., can read account info, enable trading) via the /validate endpoint."
    )
    last_validated_at: Optional[datetime] = Field(
        None,
        description="Timestamp of the last validation attempt with Binance. This is null if the key has never been validated."
    )
    created_at: datetime = Field(..., description="Timestamp when this API key record was created in our database.")
    updated_at: datetime = Field(..., description="Timestamp when this API key record was last updated (e.g., label change, status change, re-validation).")

    model_config = ConfigDict(from_attributes=True)


class DecryptedUserAPIKey(BaseModel): # For internal service use, NOT for API response
    id: int
    user_id: uuid.UUID
    binance_api_key: str # Decrypted
    binance_api_secret: str # Decrypted
    label: Optional[str]
    is_active: bool
    is_valid_on_binance: bool
```
