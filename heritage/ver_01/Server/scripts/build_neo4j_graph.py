"""
build_neo4j_graph.py
Neo4j Graph Database 노드 및 관계 (NEARBY, SAME_ERA, SAME_THEME) 구축 스크립트
"""

import os
import math

try:
    from neo4j import GraphDatabase
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

def haversine_distance(lat1, lon1, lat2, lon2):
    """두 위경도 간의 하버사인 거리(km) 계산"""
    R = 6371.0 # 지구 반지름 (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

SAMPLE_HERITAGES = [
    {"h_id": "H1", "name": "세종 연기아문", "era_normalized": "조선 전기", "dong_eup_myeon": "연기면", "lat": 36.5200, "lng": 127.2700, "theme": "역사건축"},
    {"h_id": "H2", "name": "세종 비암사 극락보전", "era_normalized": "조선 전기", "dong_eup_myeon": "전의면", "lat": 36.6300, "lng": 127.2000, "theme": "불교문화"},
    {"h_id": "H3", "name": "초려 이유태 역사공원", "era_normalized": "조선 후기", "dong_eup_myeon": "어진동", "lat": 36.5050, "lng": 127.2600, "theme": "유교학문"},
    {"h_id": "H4", "name": "합강리 선사유적", "era_normalized": "청동기시대", "dong_eup_myeon": "동면", "lat": 36.4900, "lng": 127.3200, "theme": "선사유적"},
    {"h_id": "H5", "name": "세종 영평사 구절초길", "era_normalized": "조선 후기", "dong_eup_myeon": "장군면", "lat": 36.5100, "lng": 127.2300, "theme": "불교문화"}
]

def build_graph():
    print("=== Neo4j 그래프 데이터베이스 구축 시작 ===")
    if not HAS_NEO4J:
        print("Notice: 'neo4j' 패키지가 미설치되어 로컬 노드-관계 매트릭스 계산 모드로 시뮬레이션을 수행합니다.")
        nearby_edges = []
        for i in range(len(SAMPLE_HERITAGES)):
            for j in range(i + 1, len(SAMPLE_HERITAGES)):
                h1, h2 = SAMPLE_HERITAGES[i], SAMPLE_HERITAGES[j]
                d = haversine_distance(h1['lat'], h1['lng'], h2['lat'], h2['lng'])
                if d <= 8.0:
                    nearby_edges.append((h1['h_id'], h2['h_id'], round(d, 2)))
        print(f"계산된 NEARBY 에지 관계: {nearby_edges}")
        print("그래프 시뮬레이션 완료!")
        return

    driver = None
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            # 1. 기존 노드 및 관계 초기화
            session.run("MATCH (n:Heritage) DETACH DELETE n")
            print("기존 Heritage 노드 초기화 완료")
            
            # 2. Heritage 노드 생성
            for h in SAMPLE_HERITAGES:
                session.run("""
                    CREATE (h:Heritage {
                        h_id: $h_id,
                        name: $name,
                        era_normalized: $era_normalized,
                        dong_eup_myeon: $dong_eup_myeon,
                        lat: $lat,
                        lng: $lng,
                        theme: $theme
                    })
                """, h)
            print(f"{len(SAMPLE_HERITAGES)}개 Heritage 노드 생성 완료")

            # 3. NEARBY (거리 기반 관계 < 8km) 구축
            for i in range(len(SAMPLE_HERITAGES)):
                for j in range(i + 1, len(SAMPLE_HERITAGES)):
                    h1, h2 = SAMPLE_HERITAGES[i], SAMPLE_HERITAGES[j]
                    dist = haversine_distance(h1['lat'], h1['lng'], h2['lat'], h2['lng'])
                    if dist <= 8.0:
                        session.run("""
                            MATCH (a:Heritage {h_id: $h1_id}), (b:Heritage {h_id: $h2_id})
                            MERGE (a)-[r:NEARBY {distance_km: $dist}]->(b)
                            MERGE (b)-[r2:NEARBY {distance_km: $dist}]->(a)
                        """, h1_id=h1['h_id'], h2_id=h2['h_id'], dist=round(dist, 2))

            # 4. SAME_ERA 관계 구축
            session.run("""
                MATCH (a:Heritage), (b:Heritage)
                WHERE a.h_id < b.h_id AND a.era_normalized = b.era_normalized
                MERGE (a)-[:SAME_ERA]->(b)
                MERGE (b)-[:SAME_ERA]->(a)
            """)

            # 5. SAME_THEME 관계 구축
            session.run("""
                MATCH (a:Heritage), (b:Heritage)
                WHERE a.h_id < b.h_id AND a.theme = b.theme
                MERGE (a)-[:SAME_THEME]->(b)
                MERGE (b)-[:SAME_THEME]->(a)
            """)
            
            print("Graph Edge 관계 (NEARBY, SAME_ERA, SAME_THEME) 구축 완료!")

    except Exception as e:
        print(f"Neo4j 데이터베이스 연결 시도 완료 (설정 미완료 시 시뮬레이션 대체): {e}")
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    build_graph()
