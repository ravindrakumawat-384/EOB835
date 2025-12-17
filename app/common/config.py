from pydantic import BaseSettings, Field
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "eob_db_test"
    APP_NAME: str = "EOB-835"

    # JWT
    JWT_SECRET: str = Field("cc50ec6192f5f20c2931a99dd3ab22625df90527af1b56fc2d5516dff3c43e6b", env="JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Password reset token expiry (minutes)
    RESET_TOKEN_EXPIRE_MINUTES: int = 300

    # Email stub "from"
    DEFAULT_FROM_EMAIL: str = "noreply@eob.example"
    CORS_ORIGINS: Optional[str] = "*"

    # Frontend URL used to build password reset links. Override in .env
    FRONTEND_URL: Optional[str] = "http://localhost:4200"

    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION")
    S3_BUCKET = os.getenv("S3_BUCKET")


    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

