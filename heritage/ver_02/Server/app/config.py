# config.py - ver_02 Backend Configuration

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "세종시 AI 문화유산 스마트 플랫폼 API (ver_02)"
    DEBUG: bool = False
    PORT: int = 8080
    
    # Supabase Credentials
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # LLM Settings (OpenAI / Gemini API keys)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Web API settings
    NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET", "")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
