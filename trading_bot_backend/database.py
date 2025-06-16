from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL_FROM_ENV = None
try:
    from trading_bot_backend.bot.env import DATABASE_URL as ENV_DB_URL
    DATABASE_URL_FROM_ENV = ENV_DB_URL
    logger.info(f'Successfully imported DATABASE_URL from env.py: {DATABASE_URL_FROM_ENV[:20]}...')
except ImportError:
    logger.warning('Could not import DATABASE_URL from trading_bot_backend.bot.env. Falling back to os.getenv.')
    DATABASE_URL_FROM_ENV = os.getenv('DATABASE_URL')

if not DATABASE_URL_FROM_ENV:
    logger.critical('CRITICAL: DATABASE_URL is not configured. Please set it in env.py or as an environment variable.')
    # Fallback to a local SQLite DB for development if no URL is set at all, to allow app to run.
    # However, this should be explicitly chosen by the developer.
    # DATABASE_URL_FOR_ENGINE = 'sqlite:///./trading_bot_dev.db'
    # logger.info(f'Defaulting to local SQLite for development: {DATABASE_URL_FOR_ENGINE}')
    DATABASE_URL_FOR_ENGINE = None # Explicitly None, forcing user configuration
elif 'user:password@host:port/dbname' in DATABASE_URL_FROM_ENV or not DATABASE_URL_FROM_ENV.strip():
    logger.warning(f'DATABASE_URL is using the placeholder value or is empty: {DATABASE_URL_FROM_ENV[:30]}...')
    DATABASE_URL_FOR_ENGINE = None # Explicitly None, forcing user configuration
else:
    DATABASE_URL_FOR_ENGINE = DATABASE_URL_FROM_ENV

if DATABASE_URL_FOR_ENGINE:
    if 'sqlite' in DATABASE_URL_FOR_ENGINE:
        engine = create_engine(DATABASE_URL_FOR_ENGINE, connect_args={'check_same_thread': False})
    else:
        engine = create_engine(DATABASE_URL_FOR_ENGINE)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(f'Database engine created for URL (type: {"sqlite" if "sqlite" in DATABASE_URL_FOR_ENGINE else "postgresql"}).')
else:
    logger.critical('Database engine NOT created. Application will likely fail on DB operations.')
    # Provide a dummy SessionLocal if engine is None, so app can load, but DB calls will fail.
    engine = None # type: ignore
    def SessionLocal(): raise RuntimeError('Database not configured.') # type: ignore

Base = declarative_base()

def get_db():
    if not engine:
        logger.error('Attempted to get DB session, but engine is not initialized.')
        raise RuntimeError('Database not configured, cannot provide session.')
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
