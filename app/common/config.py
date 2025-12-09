from pydantic import BaseSettings, Field
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
import os
# Load environment variables from .env file
load_dotenv()
    
# Get OpenAI API key from environment variable (.env file)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "eob_db"
    APP_NAME: str = "EOB-835"

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = os.getenv("JWT_SECRET")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = os.getenv("JWT_SECRET")
    REFRESH_TOKEN_EXPIRE_DAYS: int = os.getenv("JWT_SECRET")

    # Password reset token expiry (minutes)
    RESET_TOKEN_EXPIRE_MINUTES: int = os.getenv("RESET_TOKEN_EXPIRE_MINUTES")

    # Email stub "from"
    DEFAULT_FROM_EMAIL: str = os.getenv("DEFAULT_FROM_EMAIL")
    CORS_ORIGINS: Optional[str] = "*"

    # AWS S3 Configuration
    S3_BUCKET = os.getenv("S3_BUCKET")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION")

    
    #Openai key
    OPENAI_API_KEY = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

