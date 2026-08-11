// Code.gs - ver_02 Google Apps Script Supervisor Backend Proxy

function doGet(e) {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('전국 스마트 문화유산 통합 플랫폼 - 관리자 대시보드')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// Config variables fallback (Users should configure BACKEND_URL in Script Properties)
function getBackendUrl() {
  var props = PropertiesService.getScriptProperties();
  return props.getProperty("BACKEND_URL") || "https://heritage-react-538192513096.us-central1.run.app";
}

/**
 * Get current Google User Email from Active Session
 */
function getCurrentGoogleUserGAS() {
  try {
    var email = Session.getActiveUser().getEmail();
    if (email) {
      return { status: 'success', email: email, nickname: email.split('@')[0] };
    }
  } catch(e) {}
  return { status: 'fallback', email: 'guest@sejong.go.kr', nickname: '게스트' };
}

/**
 * Upsert user registration profile through backend proxy
 */
function upsertUserProfileGAS(email, nickname, provider) {
  var backendUrl = getBackendUrl();
  var payload = {
    email: email,
    nickname: nickname,
    auth_provider: provider || 'google'
  };
  
  try {
    var res = UrlFetchApp.fetch(backendUrl + "/api/v1/db/user-profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    if (res.getResponseCode() === 200) {
      return JSON.parse(res.getContentText());
    } else {
      return { status: 'error', message: res.getContentText() };
    }
  } catch (err) {
    return { status: 'error', message: err.toString() };
  }
}

/**
 * Fetch data for citizen recommendations and official heritages through backend proxy
 */
function getInitialWebAppData() {
  var backendUrl = getBackendUrl();
  try {
    var res = UrlFetchApp.fetch(backendUrl + "/api/v1/db/initial-data?role=supervisor", {
      method: "GET",
      muteHttpExceptions: true
    });
    
    if (res.getResponseCode() === 200) {
      return JSON.parse(res.getContentText());
    }
  } catch (e) {
    Logger.log("Error loading supervisor app data: " + e);
  }
  return { official: [], citizen: [], courses: [] };
}

/**
 * Update the vetting status of a citizen recommendation through backend proxy
 */
function updateRecommendationStatusGAS(id, newStatus) {
  var backendUrl = getBackendUrl();
  var payload = {
    status: newStatus
  };
  
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/citizen-recommendation/" + id + "/status", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200 || response.getResponseCode() === 204) {
      return JSON.parse(response.getContentText());
    } else {
      return { status: "error", message: response.getContentText() };
    }
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

/**
 * Get simple statistics of table rows for the dashboard counters through backend proxy
 */
function getDatabaseStatsGAS() {
  var backendUrl = getBackendUrl();
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/stats", {
      method: "GET",
      muteHttpExceptions: true
    });
    if (response.getResponseCode() === 200) {
      return JSON.parse(response.getContentText());
    }
  } catch (e) {
    Logger.log("Error loading stats: " + e);
  }
  return { official_count: 0, citizen_pending: 0, citizen_approved: 0 };
}

/**
 * Insert new official heritage item into database through backend proxy
 */
function insertOfficialHeritageGAS(item) {
  var backendUrl = getBackendUrl();
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/official-heritage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      payload: JSON.stringify(item),
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200 || response.getResponseCode() === 201) {
      return JSON.parse(response.getContentText());
    } else {
      return { status: "error", message: response.getContentText() };
    }
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

/**
 * Check backend database configuration health status
 */
function checkGasDbConfigurationStatus() {
  var backendUrl = getBackendUrl();
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/health", {
      method: "GET",
      muteHttpExceptions: true
    });
    if (response.getResponseCode() === 200) {
      return JSON.parse(response.getContentText());
    }
  } catch (e) {
    return { configured: false, working: false, url: "", error: e.toString() };
  }
  return { configured: false, working: false, url: "", error: "Server response error" };
}

/**
 * Sign up user with email and password through backend proxy
 */
function signUpUserWithPasswordGAS(email, password) {
  var backendUrl = getBackendUrl();
  var payload = {
    email: email,
    password: password
  };
  
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200) {
      return JSON.parse(response.getContentText());
    } else {
      return { status: "error", message: response.getContentText() };
    }
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

/**
 * Log in user with email and password through backend proxy
 */
function loginUserWithPasswordGAS(email, password) {
  var backendUrl = getBackendUrl();
  var payload = {
    email: email,
    password: password
  };
  
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200) {
      return JSON.parse(response.getContentText());
    } else {
      return { status: "error", message: response.getContentText() };
    }
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

/**
 * Get current Kakao User Mock from Active Session
 */
function getCurrentKakaoUserGAS() {
  return { status: 'success', email: 'kakao_user@kakao.com', nickname: '카카오프렌즈' };
}

/**
 * Get current Naver User Mock from Active Session
 */
function getCurrentNaverUserGAS() {
  return { status: 'success', email: 'naver_user@naver.com', nickname: '네이버그린' };
}
