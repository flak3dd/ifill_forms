from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://formforge:password@localhost:5432/formforge"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI Services
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    
    # Local AI (Ollama) - Fallback for privacy/cost control
    OLLAMA_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_VISION_MODEL: str = "llava"
    
    # Browser Configuration
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000
    BROWSER_CONCURRENCY: int = 5
    ANTI_BOT_ENABLED: bool = True
    ANTI_BOT_MODE: str = "advanced"
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # Proxy Configuration
    PROXY_ENABLED: bool = False
    PROXY_ROTATION_URL: Optional[str] = None
    
    # CAPTCHA Services
    CAPTCHA_SERVICE: Optional[str] = None  # "2captcha", "anticaptcha", etc.
    CAPTCHA_API_KEY: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/formforge.log"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
