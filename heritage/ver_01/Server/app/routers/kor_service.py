"""
app/routers/kor_service.py
한국관광공사 (KorService2) OpenAPI 연동 전용 라우터
"""

import urllib.request
import urllib.parse
import json
from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
from app.config import settings

router = APIRouter(prefix="/api/v1/kor-service", tags=["kor-service"])

OPERATIONS_MAP = [
    {
        "id": "searchKeyword2",
        "name": "키워드 검색 (searchKeyword2)",
        "description": "명소, 관광지, 문화유산 키워드 기반 정보 검색"
    },
    {
        "id": "areaBasedList2",
        "name": "지역기반 관광정보 조회 (areaBasedList2)",
        "description": "지역(세종시 등) 기반 관광자원 및 문화유산 목록 조회"
    },
    {
        "id": "searchFestival2",
        "name": "행사/공연/축제 정보 조회 (searchFestival2)",
        "description": "세종시 및 전국 최신 축제, 행사, 공연 정보 조회"
    },
    {
        "id": "searchStay2",
        "name": "숙박 정보 조회 (searchStay2)",
        "description": "한옥, 호텔, 수련원 등 지역 숙박 시설 정보 조회"
    },
    {
        "id": "categoryCode2",
        "name": "카테고리/서비스분류 코드 조회 (categoryCode2)",
        "description": "관광/문화/레저 서비스 대중소 분류 코드 조회"
    },
    {
        "id": "areaCode2",
        "name": "지역 코드 조회 (areaCode2)",
        "description": "시도 및 시군구 행정 구역 코드 목록 조회"
    },
    {
        "id": "locationBasedList2",
        "name": "위치기반 관광정보 조회 (locationBasedList2)",
        "description": "GPS 위경도 좌표 중심 반경 내 관광자원 검색"
    },
    {
        "id": "detailCommon2",
        "name": "관광정보 공통 상세 조회 (detailCommon2)",
        "description": "콘텐츠 ID 기준 개요, 개장시간, 홈페이지, 위치 상세 조회"
    }
]

@router.get("/operations")
def get_operations():
    """한국관광공사 KorService2 API 지원 기능 목록 반환"""
    return {
        "status": "success",
        "base_url": settings.KOR_SERVICE_BASE_URL,
        "operations": OPERATIONS_MAP
    }

@router.get("/search")
@router.post("/search")
def search_kor_service(
    operation: Optional[str] = Query("searchKeyword2", description="KorService2 API 연동 기능 선택"),
    keyword: Optional[str] = Query("세종", description="검색 키워드 (예: 비암사, 호수공원, 세종시)"),
    area_code: Optional[str] = Query("8", description="지역코드 (8: 세종특별자치시)"),
    content_type_id: Optional[str] = Query(None, description="관광지/문화시설/축제 분류코드"),
    content_id: Optional[str] = Query(None, description="관광정보 콘텐츠 ID"),
    num_of_rows: Optional[int] = Query(20, description="한 페이지 결과 수"),
    page_no: Optional[int] = Query(1, description="페이지 번호"),
    arrange: Optional[str] = Query("B", description="정렬구분 (A:제목순, B:인기순/조회순, C:수정일순, D:생성일순, O:대표이미지+인기순)")
):
    """한국관광공사 KorService2 OpenAPI 호출 및 수행결과 반환"""
    target_op = operation if isinstance(operation, str) and operation in [x["id"] for x in OPERATIONS_MAP] else "areaBasedList2"
    target_kw = keyword if isinstance(keyword, str) else "세종"
    target_area = area_code if isinstance(area_code, str) else "8"
    target_type = content_type_id if isinstance(content_type_id, str) else None
    target_cid = content_id if isinstance(content_id, str) else None
    target_arrange = arrange if isinstance(arrange, str) else "B"

    op = target_op
    base_url = settings.KOR_SERVICE_BASE_URL.rstrip('/')
    service_key = settings.KOR_SERVICE_API_KEY.strip()

    # Query Parameters Construct
    params = {
        "numOfRows": str(num_of_rows if isinstance(num_of_rows, int) else 20),
        "pageNo": str(page_no if isinstance(page_no, int) else 1),
        "MobileOS": "ETC",
        "MobileApp": "SejongHeritage",
        "_type": "json",
        "arrange": target_arrange
    }

    if op == "searchKeyword2":
        params["keyword"] = target_kw
        if target_area:
            params["areaCode"] = target_area
        if target_type:
            params["contentTypeId"] = target_type
    elif op == "areaBasedList2":
        if target_area:
            params["areaCode"] = target_area
        if target_type:
            params["contentTypeId"] = target_type
    elif op == "searchFestival2":
        params["eventStartDate"] = "20260101"
        if target_area:
            params["areaCode"] = target_area
    elif op == "searchStay2":
        if target_area:
            params["areaCode"] = target_area
    elif op == "categoryCode2":
        pass
    elif op == "areaCode2":
        if target_area and target_area != "all":
            params["areaCode"] = target_area
    elif op == "locationBasedList2":
        params["mapX"] = "127.281"
        params["mapY"] = "36.480"
        params["radius"] = "5000"
    elif op == "detailCommon2":
        if content_id:
            params["contentId"] = content_id
        else:
            params["contentId"] = "2825867"
        params["defaultYN"] = "Y"
        params["firstImageYN"] = "Y"
        params["addrinfoYN"] = "Y"
        params["mapinfoYN"] = "Y"
    params.pop("serviceKey", None)
    query_str = urllib.parse.urlencode(params)
    url = f"{base_url}/{op}?serviceKey={service_key}&{query_str}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SejongHeritage/1.0",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw_text = resp.read().decode('utf-8', errors='replace')
            data = json.loads(raw_text)

            items = []
            header = {}
            total_count = 0

            if isinstance(data, dict):
                body = data.get("response", {}).get("body", {})
                header = data.get("response", {}).get("header", {})
                total_count = body.get("totalCount", 0)
                items_data = body.get("items", {})
                if isinstance(items_data, dict):
                    items = items_data.get("item", [])
                elif isinstance(items_data, list):
                    items = items_data

                if isinstance(items, dict):
                    items = [items]

            # Normalize items for clear frontend rendering
            def fix_https(url_val):
                if not url_val or not isinstance(url_val, str):
                    return ""
                url_val = url_val.strip()
                if url_val.startswith("http://"):
                    return "https://" + url_val[7:]
                return url_val

            normalized = []
            for idx, item in enumerate(items):
                raw_img = fix_https(item.get("firstimage") or item.get("firstimage2") or item.get("originimgurl") or item.get("smallimageurl") or "")
                has_img = bool(raw_img and len(raw_img) > 10 and not ("unsplash.com" in raw_img))

                normalized.append({
                    "id": str(item.get("contentid") or item.get("code") or item.get("rnum") or idx),
                    "title": str(item.get("title") or item.get("name") or "세종시 관광지"),
                    "address": item.get("addr1") or item.get("addr2") or "세종특별자치시",
                    "image_url": raw_img if has_img else "",
                    "firstimage": fix_https(item.get("firstimage")),
                    "firstimage2": fix_https(item.get("firstimage2")),
                    "has_api_image": has_img,
                    "content_type_id": str(item.get("contenttypeid") or ""),
                    "createdtime": str(item.get("createdtime") or ""),
                    "modifiedtime": str(item.get("modifiedtime") or ""),
                    "tel": item.get("tel") or "정보 제공 준비 중",
                    "mapx": str(item.get("mapx") or "127.281"),
                    "mapy": str(item.get("mapy") or "36.480"),
                    "overview": item.get("overview") or item.get("catname") or "세종시 한국관광공사 OpenAPI 국문 관광정보 데이터입니다.",
                    "raw_item": item
                })

            return {
                "status": "success",
                "operation": op,
                "api_url": f"{base_url}/{op}",
                "keyword": keyword,
                "total_count": total_count or len(normalized),
                "items": normalized,
                "header": header,
                "raw_response": data
            }
    except Exception as err:
        print(f"KorService2 fetch notice ({op}): {err}")
        fallback_items = [
            {
                "id": "sejong_01",
                "title": f"세종 호수공원 ({keyword or '대표명소'})",
                "address": "세종특별자치시 연기면 호수공원길 155",
                "image_url": "",
                "has_api_image": False,
                "content_type_id": "12",
                "tel": "044-301-3921",
                "mapx": "127.268",
                "mapy": "36.497",
                "overview": "대한민국 최대 규모의 인공호수 공원으로 세종시 대표 명소입니다.",
                "raw_item": {"title": "세종 호수공원", "contentid": "sejong_01"}
            },
            {
                "id": "sejong_02",
                "title": "국립세종수목원",
                "address": "세종특별자치시 수목원로 136",
                "image_url": "",
                "has_api_image": False,
                "content_type_id": "12",
                "tel": "044-270-5000",
                "mapx": "127.284",
                "mapy": "36.495",
                "overview": "국내 최초의 도심형 국립수목원으로 사계절 온실과 전통정원을 갖추고 있습니다.",
                "raw_item": {"title": "국립세종수목원", "contentid": "sejong_02"}
            },
            {
                "id": "sejong_03",
                "title": "비암사 (세종시 보물 보유 사찰)",
                "address": "세종특별자치시 전의면 비암사길 137",
                "image_url": "",
                "has_api_image": False,
                "content_type_id": "14",
                "tel": "044-863-0490",
                "mapx": "127.202",
                "mapy": "36.634",
                "overview": "백제 구국 기원 사찰로 극락보전 및 삼층석탑 보물이 위치해 있습니다.",
                "raw_item": {"title": "비암사", "contentid": "sejong_03"}
            }
        ]

        return {
            "status": "fallback",
            "operation": op,
            "api_url": f"{base_url}/{op}",
            "keyword": keyword,
            "notice": f"OpenAPI 연동 응답 수신 실패 (오류: {str(err)}), 시뮬레이션 데이터를 반환합니다.",
            "total_count": len(fallback_items),
            "items": fallback_items,
            "raw_response": {"notice": "Fallback data active", "error": str(err)}
        }
