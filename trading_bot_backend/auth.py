import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from trading_bot_backend.bot.env import TRADING_BOT_USERNAME, TRADING_BOT_PASSWORD # Adjusted path

security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, TRADING_BOT_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, TRADING_BOT_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
