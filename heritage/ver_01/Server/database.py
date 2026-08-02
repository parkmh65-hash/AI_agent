"""
app/database.py
Supabase 및 Neo4j 클라이언트 연결 및 데이터 핸들러 (Mock Fallback 지원)
"""

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = None

try:
    from neo4j import GraphDatabase
except Exception:
    GraphDatabase = None

from app.config import settings

# Supabase Client
supabase_client = None
try:
    if create_client and settings.SUPABASE_URL and settings.SUPABASE_KEY and "your-supabase" not in settings.SUPABASE_URL:
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
except Exception as e:
    print(f"Supabase connection warning: {e}")

# Neo4j Driver
neo4j_driver = None
try:
    if GraphDatabase and settings.NEO4J_URI:
        neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
except Exception as e:
    print(f"Neo4j connection warning: {e}")

def get_supabase() -> Client:
    return supabase_client

def get_neo4j():
    return neo4j_driver
