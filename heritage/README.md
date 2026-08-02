# 세종특별자치시 AI 문화유산 스마트 플랫폼 (Monorepo)

본 프로젝트는 세종특별자치시의 문화유산 데이터를 AI(Gemini + LangChain + pgvector + Neo4j) 기반으로 분석·추천하고, 사용자 맞춤 여행 코스 제작 및 시민 참여형 문화유산 발굴 서비스를 제공하는 모노레포 아키텍처입니다.

GitHub Repository: `smleegrc47-cpu/heritage`  
Target Folder: `ver_01/`

---

## 📂 프로젝트 폴더 구조 (`ver_01/`)

```
ver_01/
├── GAS/                      # Google Apps Script (GAS) & Google Sites 신속 배포 클라이언트
│   ├── Code.gs               # GAS 서버 엔트리포인트 & UrlFetchApp 백엔드 연동
│   ├── Index.html            # Google Sites 임베딩 단일 페이지 웹앱 UI
│   ├── appsscript.json       # GAS 매니페스트 설정
│   └── README.md             # GAS & Google Sites 배포 안내
└── Server/                   # 통합 서버 코드 (NestJS + PostgreSQL & Python AI)
    ├── src/                  # NestJS TypeScript 컨트롤러, 서비스, 모듈
    ├── prisma/               # PostgreSQL DB schema.prisma & seed.ts
    ├── scripts/              # 데이터 정규화, 그래프 DB 구축, 자동 업로드 스크립트
    ├── main.py               # FastAPI 서버 메인 앱 & CORS 설정
    ├── app/                  # Python API 서버 앱 (routers, services)
    ├── package.json          # NestJS Node.js 의존성
    └── requirements.txt      # 파이썬 의존성 파일
```

---

## 🚀 깃허브 업로드 방법 (`smleegrc47-cpu/heritage/ver_01`)

### 방법 1: 자동 업로드 스크립트 실행 (권장)
터미널에서 아래 명령을 실행하고 GitHub Personal Access Token (PAT)을 입력하면 전체 파일이 `smleegrc47-cpu/heritage/ver_01/` 경로로 자동 업로드됩니다.

```bash
python scripts/upload_to_github.py
```

### 방법 2: Git 명령어를 통한 업로드
```bash
git init
git remote add origin https://github.com/smleegrc47-cpu/heritage.git
git add .
git commit -m "feat: Add Sejong Heritage AI Platform v1.0 under ver_01"
git push -u origin main
```
