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
        SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

        # Neo4j Configuration
        NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")

        # OpenAI LLM & Embedding API Key
        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

        # Gemini LLM API Key
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

        # TourAPI Keys
        TOUR_API_KEY: str = os.getenv("TOUR_API_KEY", "mock_key")
        DATA_GO_KR_API_KEY: str = os.getenv("DATA_GO_KR_API_KEY", "mock_key")

        # Kakao Map & Mobility Keys
        KAKAO_REST_API_KEY: str = os.getenv("KAKAO_REST_API_KEY", "")
        KAKAO_JAVASCRIPT_KEY: str = os.getenv("KAKAO_JAVASCRIPT_KEY", "")
        KAKAO_MOBILITY_API_KEY: str = os.getenv("KAKAO_MOBILITY_API_KEY", "")

        # TMap Keys
        TMAP_APP_KEY: str = os.getenv("TMAP_APP_KEY", "")

        # KMA (기상청) Key
        KMA_API_KEY: str = os.getenv("KMA_API_KEY", "")
        PUBLIC_DATA_API_KEY: str = os.getenv("PUBLIC_DATA_API_KEY", "")

        # Map & Agent Configs
        MAP_PROVIDER: str = os.getenv("MAP_PROVIDER", "kakao")
        MAX_AGENT_RETRY: int = int(os.getenv("MAX_AGENT_RETRY", 3))
        DEFAULT_SEARCH_K: int = int(os.getenv("DEFAULT_SEARCH_K", 10))
        DEFAULT_ROUTE_RADIUS_KM: float = float(os.getenv("DEFAULT_ROUTE_RADIUS_KM", 5.0))

        model_config = SettingsConfigDict(env_file=".env", extra="ignore")
except Exception:
    class Settings:
        APP_NAME: str = os.getenv("APP_NAME", "세종시 AI 문화유산 플랫폼 API")
        DEBUG: bool = True
        SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://nmzrxczcytkkwgpiseaj.supabase.co")
        SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5tenJ4Y3pjeXRra3dncGlzZWFqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzMzM2MDYsImV4cCI6MjA5NjkwOTYwNn0.nVQxRACIt2gUiUDstNAqolozvwr23JU5eyLNi59hCSw")
        SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        TOUR_API_KEY: str = os.getenv("TOUR_API_KEY", "mock_key")
        DATA_GO_KR_API_KEY: str = os.getenv("DATA_GO_KR_API_KEY", "mock_key")
        KAKAO_REST_API_KEY: str = os.getenv("KAKAO_REST_API_KEY", "")
        KAKAO_JAVASCRIPT_KEY: str = os.getenv("KAKAO_JAVASCRIPT_KEY", "")
        KAKAO_MOBILITY_API_KEY: str = os.getenv("KAKAO_MOBILITY_API_KEY", "")
        TMAP_APP_KEY: str = os.getenv("TMAP_APP_KEY", "")
        KMA_API_KEY: str = os.getenv("KMA_API_KEY", "")
        PUBLIC_DATA_API_KEY: str = os.getenv("PUBLIC_DATA_API_KEY", "")
        MAP_PROVIDER: str = os.getenv("MAP_PROVIDER", "kakao")
        MAX_AGENT_RETRY: int = int(os.getenv("MAX_AGENT_RETRY", 3))
        DEFAULT_SEARCH_K: int = int(os.getenv("DEFAULT_SEARCH_K", 10))
        DEFAULT_ROUTE_RADIUS_KM: float = float(os.getenv("DEFAULT_ROUTE_RADIUS_KM", 5.0))

settings = Settings()

