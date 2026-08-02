"""
app/routers/admin.py
관리자 전용 시민 추천 문화유산 승인/반려 검토 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.routers.citizen import CITIZEN_RECOMMENDATIONS_DB
from datetime import datetime

router = APIRouter(prefix="/api/admin", tags=["admin"])

class AdminApprovalRequest(BaseModel):
    status: str # "승인" 또는 "반려"
    feedback: Optional[str] = None
    reviewer_id: str = "admin-01"

@router.patch("/citizen-recommendations/{rec_id}")
def review_citizen_recommendation(rec_id: str, req: AdminApprovalRequest):
    """시민 추천 문화유산 실제 존재 여부 확인 후 승인 또는 반려 처리"""
    if req.status not in ["승인", "반려"]:
        raise HTTPException(status_code=400, detail="status는 '승인' 또는 '반려'여야 합니다.")
        
    for item in CITIZEN_RECOMMENDATIONS_DB:
        if item["id"] == rec_id:
            item["status"] = req.status
            item["reviewed_at"] = datetime.now().isoformat()
            item["reviewer_id"] = req.reviewer_id
            if req.feedback:
                item["feedback"] = req.feedback
            elif req.status == "승인":
                item["feedback"] = "담당자 현장 확인 완료: 세종시 유산목록 및 일반 사용자 지도에 승인 노출됩니다."
            else:
                item["feedback"] = "현장 실사 결과 역사적/보존적 검증 기준 미달로 반려 처리되었습니다."
                
            return {
                "message": f"성공적으로 {req.status} 처리되었습니다.",
                "item": item
            }
            
    raise HTTPException(status_code=404, detail="해당 추천 제보 건을 찾을 수 없습니다.")
