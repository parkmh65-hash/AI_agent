"""
app/config.py
환경 변수 및 시스템 설정 관리 모듈
"""

import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    class Settings(BaseSettings):
        APP_NAME: str = "세종시 AI 문화유산 플랫폼 API"
        DEBUG: bool = True
        
        # Supabase Configuration
        SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://nmzrxczcytkkwgpiseaj.supabase.co")
        SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5tenJ4Y3pjeXRra3dncGlzZWFqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzMzM2MDYsImV4cCI6MjA5NjkwOTYwNn0.nVQxRACIt2gUiUDstNAqolozvwr23JU5eyLNi59hCSw")
        
        # Neo4j Configuration
        NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
        
        # Gemini LLM API Key
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        
        # Open API Keys (공공데이터포털)
        DATA_GO_KR_API_KEY: str = os.getenv("DATA_GO_KR_API_KEY", "mock_key")
        
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")
except Exception:
    class Settings:
        APP_NAME: str = os.getenv("APP_NAME", "세종시 AI 문화유산 플랫폼 API")
        DEBUG: bool = True
        SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://nmzrxczcytkkwgpiseaj.supabase.co")
        SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5tenJ4Y3pjeXRra3dncGlzZWFqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzMzM2MDYsImV4cCI6MjA5NjkwOTYwNn0.nVQxRACIt2gUiUDstNAqolozvwr23JU5eyLNi59hCSw")
        NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        DATA_GO_KR_API_KEY: str = os.getenv("DATA_GO_KR_API_KEY", "mock_key")

settings = Settings()
