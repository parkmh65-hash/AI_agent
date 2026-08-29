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
  return props.getProperty("BACKEND_URL") || "https://ver02-backend-538192513096.asia-northeast3.run.app";
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

