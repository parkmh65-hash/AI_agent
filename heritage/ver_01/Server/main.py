"""
main.py
로컬 실행을 위한 엔트리포인트 파일입니다.
실제 어플리케이션 설정 및 CORS 정책, 라우터 정의는 app/main.py에 위치하며, 본 파일은 이를 실행하기 위한 래퍼(wrapper) 역할을 합니다.
"""

from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
