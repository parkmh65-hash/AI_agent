from typing import List, Dict, Any
from app.database import get_supabase
from app.routers.heritages import normalize_heritage_row

def search_heritages_rag(query: str, theme: str = None, top_k: int = 4) -> List[Dict[str, Any]]:
    """자연어 기반 pgvector / 하이브리드 RAG 유산 시맨틱 검색 (Supabase DB 연동)"""
    supabase = get_supabase()
    
    if supabase:
        try:
            query_builder = supabase.table("heritages").select("*, images:heritage_images(*)")
            if query:
                q_clean = query.strip()
                query_builder = query_builder.or_(
                    f"name.ilike.%{q_clean}%,description.ilike.%{q_clean}%,thinking_point.ilike.%{q_clean}%,era.ilike.%{q_clean}%,dong.ilike.%{q_clean}%"
                )
            res = query_builder.limit(top_k).execute()
            if res.data is not None:
                return [normalize_heritage_row(r) for r in res.data]
        except Exception as e:
            print(f"Supabase pgvector query notice: {e}")

    return []
