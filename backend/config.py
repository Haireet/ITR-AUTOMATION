"""
Configuration management using environment variables
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Auto ITR API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = "INSECURE-DEFAULT-KEY-CHANGE-IN-PRODUCTION"  # CHANGE THIS!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "sqlite:///./auto_itr.db"
    
    # CORS
    ALLOWED_ORIGINS: str = "*"  # Comma-separated list in production

    # Optional AI settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1/chat/completions"
    OPENAI_TIMEOUT_SECONDS: int = 25
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()
