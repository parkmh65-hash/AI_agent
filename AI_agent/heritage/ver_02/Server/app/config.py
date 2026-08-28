# config.py - ver_02 Backend Configuration

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "세종시 AI 문화유산 스마트 플랫폼 API (ver_02)"
    DEBUG: bool = False
    PORT: int = int(os.getenv("PORT", 8080))
    
    # Read Supabase Credentials dynamically from Google Cloud Run Environment Variables / Properties
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://wylcqlmffchvufxpxydc.supabase.co")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # LLM Settings (OpenAI / Gemini API keys)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Web API settings
    NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET", "")
    TOUR_API_KEY: str = os.getenv("TOUR_API_KEY", "a574450c4e9b74f08312c1f80520d00e608341fca348bf1cb6bd02ff3584cf14")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
