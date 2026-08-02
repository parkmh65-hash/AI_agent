"""
clean_data.py
세종특별자치시 문화유산 마스터 데이터 정규화 스크립트 (Pure Python & Pandas Dual Support)
"""

import re

# 시대 정규화 맵핑 매트릭스
ERA_NORMALIZATION_MAP = {
    r".*청동기.*": "청동기시대",
    r".*삼국.*|.*백제.*|.*신라(?!통일).*|.*고구려.*": "삼국시대",
    r".*통일신라.*|.*통일 신라.*": "통일신라",
    r".*고려.*": "고려",
    r".*조선.*초.*|.*조선.*전.*": "조선 전기",
    r".*조선.*중.*": "조선 중기",
    r".*조선.*후.*|.*조선.*말.*": "조선 후기",
    r".*조선.*": "조선 전기",  # 기본 조선시대 기본값
    r".*근대.*|.*일제.*|.*개항.*": "근대",
    r".*현대.*": "현대"
}

STANDARD_ERAS = [
    "청동기시대", "삼국시대", "통일신라", "고려",
    "조선 전기", "조선 중기", "조선 후기", "근대", "현대"
]

def normalize_era(era_raw: str) -> str:
    """비정규화된 시대 표기를 표준 카테고리로 정규화"""
    if not isinstance(era_raw, str) or not era_raw.strip():
        return "시대미상"
    
    clean_str = era_raw.strip()
    for pattern, std_era in ERA_NORMALIZATION_MAP.items():
        if re.match(pattern, clean_str, re.IGNORECASE):
            return std_era
            
    return "시대미상"

def extract_dong_eup_myeon(address: str) -> str:
    """소재지 주소에서 읍/면/동 추출"""
    if not isinstance(address, str) or not address.strip():
        return "기타"
    
    match = re.search(r'([가-힣]+(?:조치원읍|연기면|연동면|부강면|금남면|장군면|연서면|전의면|전동면|소정면|한솔동|도담동|아름동|고운동|보람동|새롬동|대평동|소담동|다정동|해밀동|반곡동|집현동|산울동|합강동|나성동))', address)
    if match:
        return match.group(1)
    
    # 2차 시도: 읍/면/동 단어 추출
    match_fallback = re.search(r'([가-힣]{2,5}(?:읍|면|동))', address)
    if match_fallback:
        return match_fallback.group(1)
        
    return "조치원읍"  # 기본값

def clean_heritage_item(item: dict) -> dict:
    """단일 문화유산 레코드 정규화 클렌징"""
    clean_item = dict(item)
    raw_era = item.get('era') or item.get('시대') or ''
    raw_addr = item.get('address') or item.get('소재지') or ''
    
    clean_item['era_normalized'] = normalize_era(raw_era)
    clean_item['dong_eup_myeon'] = extract_dong_eup_myeon(raw_addr)
    return clean_item

if __name__ == "__main__":
    print("=== 세종시 문화유산 데이터 클렌징 모듈 테스트 ===")
    sample_items = [
        {"H_ID": "H1", "명칭": "세종 연기아문", "소재지": "세종특별자치시 연기면 연기리 31-1", "시대": "조선시대 초", "소개": "연기현의 관아 대문..."},
        {"H_ID": "H2", "명칭": "세종 비암사 극락보전", "소재지": "세종특별자치시 전의면 다방리 512", "시대": "조선전기", "소개": "비암사 내 극락보전..."},
        {"H_ID": "H3", "명칭": "초려 이유태 역사공원", "소재지": "세종특별자치시 어진동 580", "시대": "조선 후기", "소개": "조선 후기 학자..."},
        {"H_ID": "H4", "명칭": "합강리 선사유적", "소재지": "세종특별자치시 동면 합강리", "시대": "청동기시대", "소개": "선사 시대 주거지..."}
    ]
    
    cleaned = [clean_heritage_item(i) for i in sample_items]
    for c in cleaned:
        print(f"[{c['H_ID']}] {c['명칭']} -> 원본 시대: {c['시대']} => 정규화 시대: {c['era_normalized']} | 읍면동: {c['dong_eup_myeon']}")
    print("\n클렌징 테스트 정상 완료!")
