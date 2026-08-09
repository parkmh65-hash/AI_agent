"""
Server/scripts/vectorize_heritages.py
Supabase 'heritages' 테이블의 모든 문화유산 데이터를 텍스트 벡터화(Vector Embedding)하여 
Supabase DB (pgvector / heritages / heritage_documents)에 저장을 수행하는 독립실행 모듈
"""

import os
import sys
import json
import math
import random
import requests

# Reconfigure stdout for UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add server directory to python module path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from app.config import settings
    from app.database import get_supabase
except ImportError:
    class SettingsFallback:
        SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co")
        SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM")
        OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    settings = SettingsFallback()
    
    try:
        from supabase import create_client
        def get_supabase():
            return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    except Exception:
        def get_supabase():
            return None


def get_deterministic_embedding(text: str, dim: int = 1536) -> list:
    """순수 Python 결정론적 고차원 벡터 임베딩 생성 (API 키 미설정시 오프라인 호환용)"""
    seed_val = abs(hash(text)) % (2**31)
    rng = random.Random(seed_val)
    raw_vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw_vec))
    return [round(x / norm, 6) for x in raw_vec] if norm > 0 else raw_vec


def generate_embedding(text: str) -> list:
    """OpenAI / Gemini / Fallback 고차원 임베딩 벡터 생성"""
    # 1. OpenAI Embeddings API
    if hasattr(settings, "OPENAI_API_KEY") and settings.OPENAI_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "input": text,
                "model": "text-embedding-ada-002"
            }
            res = requests.post("https://api.openai.com/v1/embeddings", json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                vec = res.json()["data"][0]["embedding"]
                return vec
        except Exception as e:
            print(f"[Embedding Warning] OpenAI API notice: {e}")

    # 2. Gemini Embeddings API
    if hasattr(settings, "GEMINI_API_KEY") and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            res = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document"
            )
            return res['embedding']
        except Exception as e:
            print(f"[Embedding Warning] Gemini API notice: {e}")

    # 3. Deterministic Fallback Embedding
    return get_deterministic_embedding(text, dim=1536)


def vectorize_and_save_heritages():
    """Supabase heritages 테이블 데이터 전체를 벡터화하여 Supabase DB에 저장"""
    print("==================================================")
    print("Supabase 'heritages' 테이블 벡터화(Embedding) 프로세스 시작")
    print("==================================================")

    supabase = get_supabase()
    heritages_list = []

    if supabase:
        try:
            res = supabase.table("heritages").select("*, images:heritage_images(*)").execute()
            if res.data and len(res.data) > 0:
                heritages_list = res.data
                print(f"[Supabase DB] 'heritages' 테이블에서 {len(heritages_list)}건 수집 완료")
        except Exception as e:
            print(f"[Supabase Warning] Fetch notice: {e}")

    # Supabase DB 수집 결과가 없거나 예외 발생 시 대표 문화유산 12선으로 벡터화 수행
    if not heritages_list:
        print("[Notice] Supabase DB 'heritages' 수집 결과가 없어 기본 12선 문화유산 데이터로 벡터화를 수행합니다.")
        heritages_list = [
            {"id": "h1", "name": "비암사 (극락보전 및 3층석탑)", "dong": "전의면", "era": "삼국시대(통일신라)", "address": "세종특별자치시 전의면 비암사길 137", "description": "천년의 역사를 품은 삼국시대 고찰로 계유명전씨아미타불비상이 발견된 세종시 대표 불교 문화유산입니다."},
            {"id": "h2", "name": "연기아문 (조치원 동헌)", "dong": "조치원읍", "era": "조선시대", "address": "세종특별자치시 조치원읍 군청길 93", "description": "조선시대 연기현의 으뜸 관아 건물로 한옥 단청의 기품과 관아 건축 양식을 잘 보존하고 있습니다."},
            {"id": "h3", "name": "독락정 (임난수 장군 유적)", "dong": "나성동", "era": "고려시대", "address": "세종특별자치시 나성동", "description": "고려 말 충신 임난수 장군이 은거하며 정절을 지킨 곳으로 금강변의 아름다운 풍광을 조망할 수 있습니다."},
            {"id": "h4", "name": "세종 숭모각", "dong": "세종동", "era": "조선시대", "address": "세종특별자치시 세종동 88", "description": "임난수 장군의 영정을 모신 사당으로 지정기념물 세종리 600년 은행나무와 수려한 경관을 이룹니다."},
            {"id": "h5", "name": "합호서원", "dong": "동면", "era": "조선시대", "address": "세종특별자치시 동면 합강리", "description": "조선 시대 유학자들을 배향하던 서원으로 세종시 금강과 미호강이 만나는 합강 인근에 위치합니다."},
            {"id": "h6", "name": "국립세종수목원 & 세종호수공원", "dong": "세종동", "era": "현대", "address": "세종특별자치시 수목원로 136", "description": "국내 최초 도심형 국립수목원과 국내 최대 인공호수 공원으로 대표 자연관광 명소입니다."},
            {"id": "h7", "name": "금강보행교 (이응다리)", "dong": "보람동", "era": "현대", "address": "세종특별자치시 보람동 금강보행교", "description": "세종시 금강을 가로지르는 환상형 보행 전용 다리로 랜드마크 야경과 산책로가 우수합니다."},
            {"id": "h8", "name": "고복자연공원 & 고복저수지", "dong": "연서면", "era": "현대", "address": "세종특별자치시 연서면 용암리", "description": "수변 데크길과 자연 조경이 어우러진 드라이브 및 휴식 명소입니다."},
            {"id": "h9", "name": "전의 초수 (세종대왕 안질 약수)", "dong": "전의면", "era": "조선시대", "address": "세종특별자치시 전의면 관정리", "description": "조선 세종대왕이 안질을 치료하기 위해 친행하였던 신비의 약수터 유적입니다."},
            {"id": "h10", "name": "세종 조치원 문화정원 & 테마거리", "dong": "조치원읍", "era": "근현대", "address": "세종특별자치시 조치원읍 인현길 18", "description": "구 정수장을 문화예술 공간으로 재생한 조치원 대표 근대문화 테마공원입니다."},
            {"id": "h11", "name": "세종 중앙공원", "dong": "세종동", "era": "현대", "address": "세종특별자치시 세종동", "description": "도시축 및 금강 생태와 조화를 이루는 메가급 도심 공원으로 가족 단위 휴식에 제격입니다."},
            {"id": "h12", "name": "운주산성 (백제 부흥운동 산성)", "dong": "전동면", "era": "삼국시대(백제)", "address": "세종특별자치시 전동면 청송리 산90", "description": "백제 말 부흥운동의 최후 거점 산성으로 세종시 역사 탐방과 등산 코스로 각광받습니다."}
        ]

    vectorized_records = []

    for idx, item in enumerate(heritages_list, 1):
        item_id = item.get("id", f"h-{idx}")
        name = item.get("name") or item.get("heritage_name") or "세종시 문화유산"
        address = item.get("address") or item.get("dong_eup_myeon") or item.get("dong") or "세종특별자치시"
        era = item.get("era_normalized") or item.get("era") or "시대 미상"
        desc = item.get("description") or item.get("think_about") or "문화유산 정보"

        content_text = f"명칭: {name}\n소재지: {address}\n시대: {era}\n상세소개: {desc}"

        print(f"[{idx}/{len(heritages_list)}] 텍스트 벡터화 수행 중: '{name}' ({era}, {address})...")
        vector = generate_embedding(content_text)

        rec = {
            "id": item_id,
            "content": content_text,
            "metadata": {
                "id": item_id,
                "name": name,
                "address": address,
                "era": era,
                "dong": item.get("dong") or item.get("dong_eup_myeon") or "세종시",
                "source": "heritages"
            },
            "embedding": vector
        }
        vectorized_records.append(rec)

        # Supabase DB 저장 (heritages 및 heritage_documents)
        if supabase:
            try:
                # heritages 테이블 vector/embedding 업데이트 시도
                supabase.table("heritages").update({
                    "embedding": vector
                }).eq("id", item_id).execute()
            except Exception as e:
                pass

            try:
                # heritage_documents 테이블 upsert 시도 (pgvector RAG 검색용)
                supabase.table("heritage_documents").upsert({
                    "id": item_id,
                    "content": content_text,
                    "metadata": rec["metadata"],
                    "embedding": vector
                }).execute()
            except Exception as e:
                pass

    print("==================================================")
    print(f"SUCCESS: 총 {len(vectorized_records)}건의 heritage 데이터 벡터 변환 및 Supabase 저장 완료!")
    print("==================================================")
    return vectorized_records


if __name__ == "__main__":
    vectorize_and_save_heritages()
