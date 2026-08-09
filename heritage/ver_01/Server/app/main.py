"""
app/main.py
세종특별자치시 AI 문화유산 플랫폼 백엔드 메인 앱
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.routers import heritages, ai, citizen, admin, courses, transport, agentic_rag, reviews, kor_service

app = FastAPI(
    title=settings.APP_NAME,
    description="세종특별자치시 문화유산 AI 분석·추천·코스 생성 및 시민 참여 플랫폼 백엔드 API",
    version="1.0.0"
)


# Guaranteed CORS Preflight & Response Middleware for Cloud Run & Google Apps Script
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response

    try:
        response = await call_next(request)
    except Exception as exc:
        response = JSONResponse(content={"detail": str(exc)}, status_code=500)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# Standard CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(heritages.router)
app.include_router(ai.router)
app.include_router(citizen.router)
app.include_router(admin.router)
app.include_router(courses.router)
app.include_router(transport.router)
app.include_router(agentic_rag.router)
app.include_router(reviews.router)
app.include_router(kor_service.router)


@app.post("/api/v1/agentic-rag")
def direct_agentic_rag_v1(req: agentic_rag.AgenticRAGRequest):
    return agentic_rag.process_agentic_rag(req)

@app.get("/api/v1/kor-service/search")
@app.post("/api/v1/kor-service/search")
def direct_kor_service_search(
    operation: str = "searchKeyword2",
    keyword: str = "세종",
    area_code: str = "36",
    content_type_id: str = None,
    content_id: str = None,
    num_of_rows: int = 20,
    page_no: int = 1,
    arrange: str = "B"
):
    return kor_service.search_kor_service(
        operation=operation,
        keyword=keyword,
        area_code=area_code,
        content_type_id=content_type_id,
        content_id=content_id,
        num_of_rows=num_of_rows,
        page_no=page_no,
        arrange=arrange
    )

@app.get("/")
def root():
    return {
        "status": "online",
        "app_name": settings.APP_NAME,
        "docs_url": "/docs"
    }

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
