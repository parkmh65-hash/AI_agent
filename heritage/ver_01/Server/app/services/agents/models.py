"""
app/services/agents/models.py
멀티 에이전트 시스템에서 사용하는 모든 Pydantic 데이터 모델 및 구조화된 출력 규격 정의
"""

from pydantic import BaseModel, Field
from typing import List, Optional

# 1. RAG Agent 데이터 모델
class HeritageSearchResult(BaseModel):
    heritage_name: str = Field(description="문화유산 공식 명칭")
    category: str = Field(description="문화재 지정 유형 (예: 시도유형문화재, 시민추천유산 등)")
    address: str = Field(description="문화재 소재 주소")
    description: str = Field(description="문화유산 상세 설명")
    historical_value: str = Field(description="역사적 의의 및 학술적 가치")
    source_url: str = Field(description="공식 정보 출처 또는 상세 페이지 URL")
    relevance_score: float = Field(description="사용자 질의와의 의미적 연관성 비율 (0.0 ~ 1.0)")
    confidence_score: float = Field(description="데이터 신뢰 수준 점수 (0.0 ~ 1.0)")

class RAGAgentResult(BaseModel):
    selected_heritages: List[HeritageSearchResult] = Field(description="최종 선정된 대표 문화유산 목록")
    confidence_score: float = Field(description="종합 RAG 검색 신뢰 점수 (0.0 ~ 1.0)")

# 2. Planner Agent 데이터 모델
class ScheduleItem(BaseModel):
    order: int = Field(description="방문 순서 (1부터 시작)")
    place_name: str = Field(description="장소 이름")
    place_type: str = Field(description="장소 구분 (heritage | attraction | food | cafe)")
    address: str = Field(description="소재지 주소")
    arrival_time: str = Field(description="예상 도착 시각 (HH:MM)")
    departure_time: str = Field(description="예상 출발 시각 (HH:MM)")
    stay_minutes: int = Field(description="해당 장소 예상 체류 시간(분)")
    travel_minutes_from_previous: int = Field(description="이전 장소로부터의 예상 이동 시간(분)")
    reason: str = Field(description="해당 시간대/일정 추천 이유")

class TravelPlan(BaseModel):
    title: str = Field(description="여행 테마 제목")
    start_time: str = Field(description="출발 시간 (HH:MM)")
    end_time: str = Field(description="종료 희망 시간 (HH:MM)")
    heritage_count: int = Field(description="포함된 문화유산 수")
    attraction_count: int = Field(description="포함된 주변 관광지 수")
    schedule: List[ScheduleItem] = Field(description="시간대별 세부 상세 일정 리스트")
    total_stay_minutes: int = Field(description="총 체류 시간(분)")
    estimated_travel_minutes: int = Field(description="총 예상 이동 소요시간(분)")

# 3. Map Agent 데이터 모델
class MapPoint(BaseModel):
    order: int = Field(description="순서 번호")
    place_name: str = Field(description="장소명")
    latitude: float = Field(description="위도 좌표")
    longitude: float = Field(description="경도 좌표")
    marker_type: str = Field(description="마커 타입 (S: 출발지 | H: 문화유산 | A: 관광지 | F: 식당 | C: 카페 | E: 종료지)")
    address: str = Field(description="주소")

class RouteSegment(BaseModel):
    start_name: str = Field(description="출발지 장소명")
    end_name: str = Field(description="목적지 장소명")
    distance_meters: int = Field(description="이동 거리 (미터)")
    duration_seconds: int = Field(description="이동 소요시간 (초)")
    path: List[List[float]] = Field(description="이동 경로 선 (Polyline 위경도 [[lat, lng], ...] 쌍의 배열)")

class MapResult(BaseModel):
    center_latitude: float = Field(description="지도 중심점 위도")
    center_longitude: float = Field(description="지도 중심점 경도")
    zoom_level: int = Field(description="지도 권장 확대 레벨 (Zoom Level)")
    markers: List[MapPoint] = Field(description="지도 상에 렌더링될 마커 좌표 및 종류 배열")
    routes: List[RouteSegment] = Field(description="각 구간별 이동선(Polyline) 및 경로 데이터 배열")
    total_distance_meters: int = Field(description="총 이동 거리 합산 (미터)")
    total_duration_seconds: int = Field(description="총 이동 소요시간 합산 (초)")

# 4. Optimization Agent 데이터 모델
class OptimizationResult(BaseModel):
    optimized_order: List[str] = Field(description="최적화된 방문 장소 이름 순서 배열")
    original_distance_km: float = Field(description="최적화 전 총 이동 거리 (km)")
    optimized_distance_km: float = Field(description="최적화 후 총 이동 거리 (km)")
    original_duration_minutes: int = Field(description="최적화 전 총 이동 소요시간 (분)")
    optimized_duration_minutes: int = Field(description="최적화 후 총 이동 소요시간 (분)")
    removed_places: List[str] = Field(description="제외 또는 탈락된 부적합 장소 배열")
    replacement_places: List[str] = Field(description="대체 추가된 장소 배열")
    optimization_score: float = Field(description="동선 최적화 평가 지수 점수 (0.0 ~ 1.0)")
    reasons: List[str] = Field(description="최적화 수행 사유 및 동선 선정 논리 설명 목록")

# 5. Personalization Agent 데이터 모델
class UserTravelProfile(BaseModel):
    travel_type: str = Field(default="family", description="가족(family) | 연인(couple) | 친구(friend) | 혼자(solo) 등")
    companions: List[str] = Field(default=[], description="동행 구성원 (adult, child, senior, pet 등)")
    age_groups: List[str] = Field(default=[], description="연령대 그룹")
    transport_type: str = Field(default="car", description="승용차(car) | 대중교통(public) | 도보(walk)")
    start_location: str = Field(default="세종시청", description="출발지 주소 또는 장소명")
    start_time: str = Field(default="09:00", description="출발 희망 시각")
    end_time: str = Field(default="19:00", description="종료 희망 시각")
    interests: List[str] = Field(default=[], description="관심 분야 (history, nature, experience, cafe 등)")
    disliked_activities: List[str] = Field(default=[], description="기피 항목")
    walking_tolerance: str = Field(default="medium", description="도보 허용 강도 (low | medium | high)")
    budget_level: str = Field(default="medium", description="예산 강도")
    meal_preferences: List[str] = Field(default=[], description="선호 음식군")
    pet_companion: bool = Field(default=False, description="반려동물 동반 여부")
    child_companion: bool = Field(default=False, description="어린이 동반 여부")
    accessibility_required: bool = Field(default=False, description="장애인/휠체어 등 무장애 시설 접근성 필요 여부")

# 6. Validation Agent 데이터 모델
class PlaceValidation(BaseModel):
    place_name: str = Field(description="검증 장소명")
    status: str = Field(description="검증 상태 (verified | needs_update | invalid | insufficient_data)")
    address_verified: bool = Field(description="공식 주소 일치 여부")
    operation_verified: bool = Field(description="운영 시간/휴관일 검증 적합 여부")
    coordinate_verified: bool = Field(description="좌표 세종시 범위 내 존재 및 정확도 일치 여부")
    source_verified: bool = Field(description="공식 출처 매칭 및 존재 신뢰 여부")
    issues: List[str] = Field(description="발견된 문제점 또는 정정 사유 리스트")
    source_urls: List[str] = Field(description="검증 참고용 공식 출처 웹 주소 목록")

class ValidationResult(BaseModel):
    overall_status: str = Field(description="종합 판정 결과 (verified | unverified | revision_needed)")
    validation_score: float = Field(description="최종 일정 정합 검증 신뢰도 지수 (0.0 ~ 1.0)")
    verified_places: int = Field(description="검증 완료된 장소 수")
    failed_places: int = Field(description="검증 실패한 장소 수")
    requires_revision: bool = Field(description="에이전트 재수행(Rewrite/Plan) 루프 복귀 필요 여부")
    revision_target: Optional[str] = Field(None, description="재수행 대상 에이전트 식별자 (rag | personalization | planner | map | optimization)")
    place_results: List[PlaceValidation] = Field(description="각 장소별 세부 검증 결과 배열")
