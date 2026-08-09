// api.js - 세종시 문화유산 스마트 플랫폼 클라이언트 API 모듈 (Google Apps Script 전용 경량화 버전)

export const CLOUD_RUN_URL = 'https://heritage-react-538192513096.us-central1.run.app';

// 1. 초기 데이터 일괄 조회 (중복 호출 제거 및 단일 채널 연동 최적화)
export function fetchInitialAppData() {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler(resolve)
      .withFailureHandler(reject)
      .getInitialWebAppData();
  });
}

// 3. 시민 제보 좋아요 동기화
export function syncHeartToSupabase(id, newHeart, itemName) {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler(resolve)
      .withFailureHandler(reject)
      .incrementCitizenHeartGAS(id, newHeart, itemName);
  });
}

// 4. 시민 제보 제출
export function submitCitizenRecommendation(payload) {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler((res) => {
        if (res && res.status === 'success') resolve(res);
        else reject(new Error(res.message || '제출 실패'));
      })
      .withFailureHandler(reject)
      .submitCitizenRecommendationGAS(payload);
  });
}

// 5. 코스 저장
export function saveCourse(coursePayload) {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler((res) => {
        if (res && res.status === 'success') resolve(res);
        else reject(new Error(res.message || '저장 실패'));
      })
      .withFailureHandler(reject)
      .saveCourseGAS(coursePayload);
  });
}

// 6. 저장된 코스 목록 조회
export function fetchSavedCourses() {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler((res) => resolve(res || []))
      .withFailureHandler(reject)
      .fetchSavedCoursesGAS(); // Fallback if initial load is not used
  });
}

// 7. 탐방 후기 저장
export function submitCourseReview(reviewPayload) {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler(resolve)
      .withFailureHandler(reject)
      .submitCourseReviewGAS(reviewPayload);
  });
}

// 8. 한국관광공사 OpenAPI 조회
export function fetchKorServiceOpenAPI(op, keyword, arrange) {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler((res) => {
        if (res && res.status === 'success' && res.data) resolve(res.data);
        else reject(new Error('OpenAPI 조회 실패'));
      })
      .withFailureHandler(reject)
      .fetchKorServiceGAS(op, keyword, arrange, '8');
  });
}

// 9. AI 5선 에이전트 RAG 쿼리
export async function queryAgenticRAG(query, areaCode) {
  const res = await fetch(`${CLOUD_RUN_URL}/api/v1/agentic-rag/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, area_code: areaCode })
  });
  if (!res.ok) throw new Error(`Agentic RAG HTTP ${res.status}`);
  return res.json();
}

// 10. AI 가이드북 및 스토리보드 생성
export async function generateGuidebook(heritageNames, transport = '승용차') {
  const res = await fetch(`${CLOUD_RUN_URL}/api/v1/guidebook`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ heritages: heritageNames, transport })
  });
  if (!res.ok) throw new Error(`Guidebook generation HTTP ${res.status}`);
  return res.json();
}

// 11. Agentic RAG Graph (Mermaid) 조회
export async function fetchAgenticGraph() {
  try {
    const res = await fetch(`${CLOUD_RUN_URL}/api/v1/agentic-rag/graph`);
    if (!res.ok) return { mermaid: '' };
    return res.json();
  } catch (err) {
    return { mermaid: '' };
  }
}

// 12. 공용 설정 및 헬스 체크
export async function fetchSystemStatus() {
  const result = { fastapi: false, supabase: true, korapi: true, supabaseCounts: { heritages: 0, images: 0, reviews: 0 } };
  try {
    const res = await fetch(`${CLOUD_RUN_URL}/health`);
    if (res.ok) result.fastapi = true;
  } catch (e) {}
  return result;
}

// 13. Supabase Storage 파일 업로드 (GAS Server proxy 호출)
export function uploadImageToSupabase(base64Data, fileName) {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler((res) => {
        if (res && res.status === 'success') resolve(res);
        else reject(new Error(res.message || '이미지 업로드 실패'));
      })
      .withFailureHandler(reject)
      .uploadImageToSupabaseStorageGAS(base64Data, fileName);
  });
}

// 14. 관리자 보고서 작성
export function generateAdminReport() {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler(resolve)
      .withFailureHandler(reject)
      .generateAdminReportGAS();
  });
}

// 15. 관리자 엑셀 데이터를 Supabase에 이관
export function importExcelToSupabaseDirect(records) {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler((res) => {
        if (res && res.status === 'success') resolve(res);
        else reject(new Error(res.message || '엑셀 이관 실패'));
      })
      .withFailureHandler(reject)
      .importExcelToSupabaseDirectGAS(records);
  });
}


// [추가] 모니터링 통계 정보 일괄 조회
export function fetchMonitoringStats() {
  return new Promise((resolve, reject) => {
    google.script.run
      .withSuccessHandler(resolve)
      .withFailureHandler(reject)
      .fetchMonitoringStatsGAS();
  });
}
