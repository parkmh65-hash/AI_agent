// Code.gs - ver_02 Google Apps Script Backend Proxy

function doGet(e) {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('전국 스마트 문화유산 통합 플랫폼')
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

// Config variables fallback (Users should configure these in Script Properties)
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
 * Fetch initial app data (both official and citizen recommendations)
 */
function getInitialWebAppData() {
  var config = getSupabaseConfig();
  var result = { official: [], citizen: [] };
  
  if (!config.key) {
    // Return mock data if Supabase credentials are missing
    result.official = [
      { id: "cit_1", name: "비암사", address: "세종시 전의면 다방리 137", latitude: 36.6345, longitude: 127.2341, description: "비암사 극락보전 등이 있는 전통 사찰", category: "사찰", source: "official" },
      { id: "cit_2", name: "조치원향교", address: "세종시 연기면 교리", latitude: 36.5982, longitude: 127.2985, description: "지방 교육 기관이었던 유서 깊은 향교", category: "교육", source: "official" }
    ];
    return result;
  }
  
  try {
    // 1. Fetch official heritages from Supabase REST API
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
    
    // 2. Fetch citizen recommendations
    var resCitizen = UrlFetchApp.fetch(config.url + "/rest/v1/citizen_recommendations?select=*", {
      method: "GET",
      headers: headers,
      muteHttpExceptions: true
    });
    
    if (resCitizen.getResponseCode() === 200) {
      result.citizen = JSON.parse(resCitizen.getContentText());
    }
  } catch (e) {
    Logger.log("Error loading app data: " + e);
  }
  
  return result;
}

/**
 * Submit new citizen recommendation item to database
 */
function submitCitizenRecommendationGAS(item) {
  var config = getSupabaseConfig();
  if (!config.key) {
    return { status: "success", message: "Mock success (No DB connection)" };
  }
  
  try {
    var headers = {
      "apikey": config.key,
      "Authorization": "Bearer " + config.key,
      "Content-Type": "application/json",
      "Prefer": "return=representation"
    };
    
    var response = UrlFetchApp.fetch(config.url + "/rest/v1/citizen_recommendations", {
      method: "POST",
      headers: headers,
      payload: JSON.stringify(item),
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 201 || response.getResponseCode() === 200) {
      return { status: "success", data: JSON.parse(response.getContentText()) };
    } else {
      return { status: "error", message: response.getContentText() };
    }
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

/**
 * Query courses list from database
 */
function fetchSavedCoursesGAS() {
  var config = getSupabaseConfig();
  if (!config.key) return [];
  
  try {
    var headers = {
      "apikey": config.key,
      "Authorization": "Bearer " + config.key
    };
    
    var response = UrlFetchApp.fetch(config.url + "/rest/v1/courses?select=*&order=created_at.desc", {
      method: "GET",
      headers: headers,
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200) {
      return JSON.parse(response.getContentText());
    }
  } catch (e) {
    Logger.log("Error loading courses: " + e);
  }
  return [];
}

/**
 * Upload Base64 image payload directly to Supabase storage bucket
 */
function uploadImageToSupabaseStorageGAS(base64Data, filename) {
  var config = getSupabaseConfig();
  if (!config.key) {
    return { status: "success", publicUrl: "https://via.placeholder.com/150" };
  }
  
  try {
    // Clean base64 metadata headers
    var base64Clean = base64Data.split(",")[1] || base64Data;
    var rawBytes = Utilities.base64Decode(base64Clean);
    
    var bucketName = "heritage-images";
    var uploadUrl = config.url + "/storage/v1/object/" + bucketName + "/" + filename;
    
    var headers = {
      "apikey": config.key,
      "Authorization": "Bearer " + config.key,
      "Content-Type": "image/jpeg"
    };
    
    var response = UrlFetchApp.fetch(uploadUrl, {
      method: "POST",
      headers: headers,
      payload: rawBytes,
      muteHttpExceptions: true
    });
    
    var code = response.getResponseCode();
    if (code === 200 || code === 201) {
      var publicUrl = config.url + "/storage/v1/object/public/" + bucketName + "/" + filename;
      return { status: "success", publicUrl: publicUrl };
    } else {
      return { status: "error", message: response.getContentText() };
    }
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}
