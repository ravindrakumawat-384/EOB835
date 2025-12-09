from pydantic import BaseSettings, Field
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "eob_db"
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

    # AWS S3 Configuration
    S3_BUCKET = "eob-dev-bucket"
    AWS_ACCESS_KEY_ID = "AKIA2GG23YNROAFON7PD"
    AWS_SECRET_ACCESS_KEY = "llMj0AtymOmtA9tbM5i7Y+3DKGv1qOyCpRg/CEVM"
    AWS_REGION = "ap-south-1"
 
    #Openai key
    OPENAI_API_KEY = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

