import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # Supabase credentials (optional, falls back to local storage)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "multimodal-rag")
    
    # Storage settings
    CHROMADB_DIR = os.getenv("CHROMADB_DIR", "./chroma_db")
    LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", "./static/extracted")
    
    # FastAPI Server settings
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))

    @classmethod
    def validate_keys(cls):
        """Validates that necessary API keys are set."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        
        # Ensure local storage directory exists
        os.makedirs(cls.LOCAL_STORAGE_DIR, exist_ok=True)
        os.makedirs(cls.CHROMADB_DIR, exist_ok=True)

config = Config()
