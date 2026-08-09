// Code.gs - ver_02 Google Apps Script Supervisor Backend Proxy

function doGet(e) {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('전국 스마트 문화유산 통합 플랫폼 - 관리자 대시보드')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(filename) {
  try {
    return HtmlService.createHtmlOutputFromFile(filename).getContent();
  } catch (err) {
    Logger.log("Include error (" + filename + "): " + err);
    return "<!-- Missing template: " + filename + " -->";
  }
}

function getSupabaseConfig() {
  var props = PropertiesService.getScriptProperties();
  return {
    url: props.getProperty("SUPABASE_URL") || "https://pdpmtgnagwzcsftavtap.supabase.co",
    key: props.getProperty("SUPABASE_KEY") || ""
  };
}

function getCloudRunBackendUrl() {
  var props = PropertiesService.getScriptProperties();
  return props.getProperty("CLOUD_RUN_URL") || "https://heritage-react-538192513096.us-central1.run.app";
}

/**
 * Fetch data for citizen recommendations and official heritages
 */
function getInitialWebAppData() {
  var config = getSupabaseConfig();
  var result = { official: [], citizen: [] };
  
  if (!config.key) {
    result.citizen = [
      { id: 1, name: "조치원 가로수", address: "세종시 조치원읍", description: "보존이 필요한 오래된 노거수 가로수길", status: "대기", user_id: "citizen1@gmail.com", latitude: 36.59, longitude: 127.29 }
    ];
    return result;
  }
  
  try {
    var headers = {
      "apikey": config.key,
      "Authorization": "Bearer " + config.key
    };
    
    var resOfficial = UrlFetchApp.fetch(config.url + "/rest/v1/heritages?select=*", {
      method: "GET",
      headers: headers,
      muteHttpExceptions: true
    });
    if (resOfficial.getResponseCode() === 200) {
      result.official = JSON.parse(resOfficial.getContentText());
    }
    
    var resCitizen = UrlFetchApp.fetch(config.url + "/rest/v1/citizen_recommendations?select=*&order=created_at.desc", {
      method: "GET",
      headers: headers,
      muteHttpExceptions: true
    });
    if (resCitizen.getResponseCode() === 200) {
      result.citizen = JSON.parse(resCitizen.getContentText());
    }
  } catch (e) {
    Logger.log("Error loading data: " + e);
  }
  return result;
}

/**
 * Update the vetting status of a citizen recommendation
 */
function updateRecommendationStatusGAS(id, newStatus) {
  var config = getSupabaseConfig();
  if (!config.key) {
    return { status: "success", id: id, newStatus: newStatus };
  }
  
  try {
    var headers = {
      "apikey": config.key,
      "Authorization": "Bearer " + config.key,
      "Content-Type": "application/json"
    };
    
    var url = config.url + "/rest/v1/citizen_recommendations?id=eq." + id;
    var payload = { "status": newStatus };
    
    var response = UrlFetchApp.fetch(url, {
      method: "PATCH",
      headers: headers,
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 204 || response.getResponseCode() === 200) {
      return { status: "success", id: id, newStatus: newStatus };
    } else {
      return { status: "error", message: response.getContentText() };
    }
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

/**
 * Get simple statistics of table rows for the dashboard counters
 */
function getDatabaseStatsGAS() {
  var config = getSupabaseConfig();
  var stats = { official_count: 0, citizen_pending: 0, citizen_approved: 0 };
  
  if (!config.key) {
    return { official_count: 5, citizen_pending: 1, citizen_approved: 0 };
  }
  
  try {
    var headers = {
      "apikey": config.key,
      "Authorization": "Bearer " + config.key
    };
    
    var resOfficial = UrlFetchApp.fetch(config.url + "/rest/v1/heritages?select=id", {
      method: "GET",
      headers: headers,
      muteHttpExceptions: true
    });
    if (resOfficial.getResponseCode() === 200) {
      stats.official_count = JSON.parse(resOfficial.getContentText()).length;
    }
    
    var resPending = UrlFetchApp.fetch(config.url + "/rest/v1/citizen_recommendations?status=eq.대기&select=id", {
      method: "GET",
      headers: headers,
      muteHttpExceptions: true
    });
    if (resPending.getResponseCode() === 200) {
      stats.citizen_pending = JSON.parse(resPending.getContentText()).length;
    }

    var resApproved = UrlFetchApp.fetch(config.url + "/rest/v1/citizen_recommendations?status=eq.승인&select=id", {
      method: "GET",
      headers: headers,
      muteHttpExceptions: true
    });
    if (resApproved.getResponseCode() === 200) {
      stats.citizen_approved = JSON.parse(resApproved.getContentText()).length;
    }
  } catch (e) {
    Logger.log("Error loading stats: " + e);
  }
  return stats;
}
