"""
upload_to_github.py
GitHub REST API를 사용하여 smleegrc47-cpu/heritage 리포지토리의 ver_01 폴더 및 루트 .github/workflows 로 소스코드를 업로드하는 스크립트
"""

import os
import json
import base64
import ssl
import urllib.request
import urllib.error

REPO_OWNER = "smleegrc47-cpu"
REPO_NAME = "heritage"
TARGET_FOLDER = "ver_01"

EXCLUDE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'temp_images', 'dist', 'build'}
EXCLUDE_FILES = {'.DS_Store', 'desktop.ini'}

ssl_context = ssl._create_unverified_context()

def upload_file_to_github(file_path: str, repo_path: str, token: str, retries: int = 3):
    """GitHub Contents API를 사용하여 단일 파일 업로드 (409 충돌 발생 시 자동 재시도)"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{repo_path}"
    
    with open(file_path, "rb") as f:
        content = f.read()
    
    encoded_content = base64.b64encode(content).decode("utf-8")
    
    for attempt in range(retries):
        sha = None
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Antigravity-Agent",
                "Accept": "application/vnd.github+json"
            })
            with urllib.request.urlopen(req, context=ssl_context) as resp:
                data = json.loads(resp.read().decode())
                sha = data.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"Notice checking {repo_path}: HTTP {e.code}")
        except Exception:
            pass

        payload = {
            "message": f"Upload {repo_path} to repository",
            "content": encoded_content
        }
        if sha:
            payload["sha"] = sha

        data_json = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_json,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "Antigravity-Agent",
                "Accept": "application/vnd.github+json"
            },
            method="PUT"
        )

        try:
            with urllib.request.urlopen(req, context=ssl_context) as resp:
                print(f"[SUCCESS] {repo_path} 업로드 완료!")
                return True
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode()
            if e.code == 409 and attempt < retries - 1:
                print(f"[RETRY] {repo_path} 409 충돌 발생, 최신 sha 재동기화 후 재시도 ({attempt+1}/{retries})...")
                continue
            print(f"[FAIL] {repo_path} 업로드 실패 (HTTP {e.code}): {err_msg}")
            return False
        except Exception as e:
            print(f"[FAIL] {repo_path} Exception: {e}")
            return False
    return False

def upload_all_sources(token: str, base_dir: str = "."):
    """전체 소스코드 파일 (backend, frontend, gas, scripts 등) 업로드"""
    print(f"=== {REPO_OWNER}/{REPO_NAME} 깃허브 업로드 및 Cloud Run CI/CD 재설정 시작 ===")
    
    upload_count = 0
    fail_count = 0
    
    # 1. 루트 레벨 .github/workflows/deploy-cloudrun.yml 파일 업로드 (GitHub Actions 인식 필수)
    workflow_local = os.path.join(base_dir, ".github", "workflows", "deploy-cloudrun.yml")
    if os.path.exists(workflow_local):
        print("업로드 진행 중 (루트 워크플로우): .github/workflows/deploy-cloudrun.yml")
        if upload_file_to_github(workflow_local, ".github/workflows/deploy-cloudrun.yml", token):
            upload_count += 1
        else:
            fail_count += 1

    # 2. 소스 파일 업로드 (루트 및 ver_01 동시 업데이트)
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f in EXCLUDE_FILES or f.endswith('.pyc'):
                continue
            
            local_path = os.path.join(root, f)
            rel_path = os.path.relpath(local_path, base_dir).replace("\\", "/")
            
            # 업로드 경로 목록 (루트 및 ver_01 폴더 구조 모두 커버)
            repo_paths = [rel_path, f"{TARGET_FOLDER}/{rel_path}"]
            for repo_path in repo_paths:
                print(f"업로드 진행 중: {rel_path} -> {repo_path}")
                if upload_file_to_github(local_path, repo_path, token):
                    upload_count += 1
                else:
                    fail_count += 1

    print(f"\n[결과] 성공: {upload_count}개 파일, 실패: {fail_count}개 파일")

if __name__ == "__main__":
    import sys
    token = None
    if "--token" in sys.argv:
        idx = sys.argv.index("--token")
        if idx + 1 < len(sys.argv):
            token = sys.argv[idx + 1]
            
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            token = input("GitHub Personal Access Token (PAT)을 입력하세요: ").strip()
        except Exception:
            token = None
            
    if token:
        upload_all_sources(token)
    else:
        print("토큰이 입력되지 않아 업로드를 중단합니다.")
