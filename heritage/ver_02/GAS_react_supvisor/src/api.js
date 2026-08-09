// api.js - ver_02 Supervisor Client APIs

export const CLOUD_RUN_URL = 'https://heritage-react-538192513096.us-central1.run.app';

function callGasMethod(methodName, ...args) {
  return new Promise((resolve, reject) => {
    if (typeof google !== 'undefined' && google.script && google.script.run) {
      google.script.run
        .withSuccessHandler(resolve)
        .withFailureHandler(reject)[methodName](...args);
    } else {
      console.warn(`[Local Fallback] GAS method ${methodName} called.`);
      if (methodName === 'getInitialWebAppData') {
        resolve({ official: [], citizen: [] });
      } else if (methodName === 'getDatabaseStatsGAS') {
        resolve({ official_count: 5, citizen_pending: 1, citizen_approved: 0 });
      } else {
        resolve({ status: 'success' });
      }
    }
  });
}

export function fetchInitialAppData() {
  return callGasMethod('getInitialWebAppData');
}

export function updateRecommendationStatus(id, newStatus) {
  return callGasMethod('updateRecommendationStatusGAS', id, newStatus);
}

export function getDatabaseStats() {
  return callGasMethod('getDatabaseStatsGAS');
}

/**
 * Call backend fastapi server health status
 */
export async function getBackendHealthStatus() {
  try {
    const res = await fetch(`${CLOUD_RUN_URL}/health`, { method: "GET" });
    if (res.ok) {
      return await res.json();
    }
    throw new Error(`HTTP Error ${res.status}`);
  } catch (err) {
    console.error("Backend health check failed:", err);
    throw err;
  }
}
