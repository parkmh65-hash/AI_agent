// Code.gs - ver_02 Google Apps Script Backend Proxy

function doGet(e) {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('전국 스마트 문화유산 통합 플랫폼')
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
    if (!email) {
      email = Session.getEffectiveUser().getEmail();
    }
    if (email && email.indexOf('@') !== -1) {
      return { status: 'success', email: email, nickname: email.split('@')[0] };
    }
  } catch(e) {}
  return { status: 'fallback', email: '', nickname: '' };
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
 * Fetch initial app data from backend proxy
 */
function getInitialWebAppData() {
  var backendUrl = getBackendUrl();
  try {
    var res = UrlFetchApp.fetch(backendUrl + "/api/v1/db/initial-data?role=user", {
      method: "GET",
      muteHttpExceptions: true
    });
    
    if (res.getResponseCode() === 200) {
      return JSON.parse(res.getContentText());
    }
  } catch (e) {
    Logger.log("Error loading app data: " + e);
  }
  return { official: [], citizen: [] };
}

/**
 * Submit new citizen recommendation item to database through backend proxy
 */
function submitCitizenRecommendationGAS(item) {
  var backendUrl = getBackendUrl();
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/citizen-recommendation", {
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
 * Query courses list from database through backend proxy
 */
/**
 * Query courses list from database through backend proxy
 */
function fetchSavedCoursesGAS() {
  var backendUrl = getBackendUrl();
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/initial-data?role=supervisor", {
      method: "GET",
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200) {
      var data = JSON.parse(response.getContentText());
      return data.courses || [];
    }
  } catch (e) {
    Logger.log("Error loading courses: " + e);
  }
  return [];
}

/**
 * Fetch saved courses for specific user email from database
 */
function fetchUserCoursesGAS(userEmail) {
  var backendUrl = getBackendUrl();
  var targetUser = userEmail || "guest@sejong.go.kr";
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/user-courses?user_id=" + encodeURIComponent(targetUser), {
      method: "GET",
      muteHttpExceptions: true
    });
    if (response.getResponseCode() === 200) {
      var resData = JSON.parse(response.getContentText());
      return resData.courses || [];
    }
  } catch (e) {
    Logger.log("Error loading user courses: " + e);
  }
  return [];
}

/**
 * Save user generated course recommendation to database
 */
function saveUserCourseGAS(courseData) {
  var backendUrl = getBackendUrl();
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/save-course", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      payload: JSON.stringify(courseData),
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
 * Delete a user's saved course
 */
function deleteUserCourseGAS(courseId, userEmail) {
  var backendUrl = getBackendUrl();
  var targetUser = userEmail || "guest@sejong.go.kr";
  try {
    var response = UrlFetchApp.fetch(backendUrl + "/api/v1/db/delete-course?course_id=" + courseId + "&user_id=" + encodeURIComponent(targetUser), {
      method: "DELETE",
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
