from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    # Extra fields to match .env and environment variables (must be uppercase for Pydantic v2)
    OPENAI_MODEL: Optional[str] = None
    OPENAI_TEMPERATURE: Optional[float] = None
    OPENAI_MAX_TOKENS: Optional[int] = None
    MONGODB_URL: Optional[str] = None
    POSTGRES_URL: Optional[str] = None
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "eob_db_test"
    APP_NAME: str = "EOB-835"

    # JWT
    JWT_SECRET: str = Field("cc50ec6192f5f20c2931a99dd3ab22625df90527af1b56fc2d5516dff3c43e6b", env="JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Password reset token expiry (minutes)
    RESET_TOKEN_EXPIRE_MINUTES: int = 300

    # Email stub "from"
    DEFAULT_FROM_EMAIL: str = "noreply@eob.example"
    CORS_ORIGINS: Optional[str] = "*"

    # Frontend URL used to build password reset links. Override in .env
    FRONTEND_URL: Optional[str] = "http://localhost:4200"

    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    S3_BUCKET: Optional[str] = None

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = None  


    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

