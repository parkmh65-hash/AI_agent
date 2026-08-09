// api.js - ver_02 Apps Script & FastAPI Client Service APIs

export const CLOUD_RUN_URL = 'https://heritage-react-538192513096.us-central1.run.app';

/**
 * Execute GAS function with Promise wrappers
 */
function callGasMethod(methodName, ...args) {
  return new Promise((resolve, reject) => {
    if (typeof google !== 'undefined' && google.script && google.script.run) {
      google.script.run
        .withSuccessHandler(resolve)
        .withFailureHandler(reject)[methodName](...args);
    } else {
      console.warn(`[Local Fallback] GAS method ${methodName} called.`);
      // Mock local responses for development
      if (methodName === 'getInitialWebAppData') {
        resolve({ official: [], citizen: [] });
      } else if (methodName === 'fetchSavedCoursesGAS') {
        resolve([]);
      } else {
        resolve({ status: 'success' });
      }
    }
  });
}

export function fetchInitialAppData() {
  return callGasMethod('getInitialWebAppData');
}

export function submitCitizenRecommendation(item) {
  return callGasMethod('submitCitizenRecommendationGAS', item);
}

export function fetchSavedCourses() {
  return callGasMethod('fetchSavedCoursesGAS');
}

export function uploadImageToSupabaseStorage(base64Data, filename) {
  return callGasMethod('uploadImageToSupabaseStorageGAS', base64Data, filename);
}

/**
 * Call FastAPI agentic RAG query backend
 */
export async function executeRAGQuery(query, areaCode = "전체") {
  try {
    const res = await fetch(`${CLOUD_RUN_URL}/api/v1/agentic-rag/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ query, area_code: areaCode })
    });
    if (res.ok) {
      return await res.json();
    }
    throw new Error(`HTTP Status Error ${res.status}`);
  } catch (err) {
    console.error("FastAPI RAG error:", err);
    throw err;
  }
}

/**
 * Call FastAPI guidebook generation backend
 */
export async function generateGuidebook(heritages, transport = "승용차") {
  try {
    const res = await fetch(`${CLOUD_RUN_URL}/api/v1/guidebook`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ heritages, transport })
    });
    if (res.ok) {
      return await res.json();
    }
    throw new Error(`HTTP Status Error ${res.status}`);
  } catch (err) {
    console.error("FastAPI Guidebook error:", err);
    throw err;
  }
}
