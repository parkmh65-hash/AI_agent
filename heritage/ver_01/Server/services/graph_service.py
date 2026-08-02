"""
app/services/graph_service.py
Neo4j Graph 기반 문화유산 연관 관계 (거리, 동일시대, 동일테마) 분석 및 코스 추천 서비스
"""

from typing import List, Dict, Any
from app.database import get_neo4j, get_supabase

def recommend_course_graph(start_heritage_id: str, max_items: int = 3) -> List[Dict[str, Any]]:
    """Neo4j 및 Supabase DB를 조회하여 연관 문화유산 추천"""
    driver = get_neo4j()
    supabase = get_supabase()
    
    all_heritages = []
    if supabase:
        try:
            res = supabase.table("heritages").select("*, images:heritage_images(*)").execute()
            if res.data:
                all_heritages = res.data
        except Exception as e:
            print(f"Supabase query notice: {e}")

    if not all_heritages:
        return []

    if driver:
        try:
            with driver.session() as session:
                query = """
                MATCH (start:Heritage {h_id: $start_id})
                MATCH (start)-[r:NEARBY|SAME_ERA|SAME_THEME]-(related:Heritage)
                RETURN related.h_id AS h_id, related.name AS name, type(r) AS rel_type, r.distance_km AS dist
                LIMIT $limit
                """
                res = session.run(query, start_id=start_heritage_id, limit=max_items)
                records = [record.data() for record in res]
                if records:
                    matched_ids = [r['h_id'] for r in records]
                    return [h for h in all_heritages if h.get('h_id') in matched_ids or h.get('id') == start_heritage_id]
        except Exception as e:
            print(f"Neo4j Query Notice: {e}")

    start_item = next((h for h in all_heritages if h.get('h_id') == start_heritage_id or h.get('id') == start_heritage_id), all_heritages[0])
    
    recommendations = [start_item]
    for candidate in all_heritages:
        if candidate.get('id') != start_item.get('id'):
            if candidate.get('era') == start_item.get('era') or candidate.get('dong') == start_item.get('dong'):
                recommendations.append(candidate)
        if len(recommendations) >= max_items:
            break
            
    return recommendations
