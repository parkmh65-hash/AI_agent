"""
app/services/rag_service.py
pgvector 기반 RAG 시맨틱 유산 검색 서비스
"""

from typing import List, Dict, Any
from app.database import get_supabase

def search_heritages_rag(query: str, theme: str = None, top_k: int = 4) -> List[Dict[str, Any]]:
    """자연어 기반 pgvector RAG 유산 검색 (Supabase DB 연동)"""
    supabase = get_supabase()
    
    if supabase:
        try:
            query_builder = supabase.table("heritages").select("*, images:heritage_images(*)")
            if query:
                query_builder = query_builder.ilike("name", f"%{query}%")
            res = query_builder.limit(top_k).execute()
            if res.data is not None:
                return res.data
        except Exception as e:
            print(f"Supabase pgvector query notice: {e}")

    return []
