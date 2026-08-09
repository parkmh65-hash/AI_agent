// Code.gs - ver_02 Google Apps Script Supervisor Backend Proxy

function doGet(e) {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('전국 스마트 문화유산 통합 플랫폼 - 관리자 대시보드')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getSupabaseConfig() {
  var props = PropertiesService.getScriptProperties();
  return {
    url: props.getProperty("SUPABASE_URL") || "https://pdpmtgnagwzcsftavtap.supabase.co",
    key: props.getProperty("SUPABASE_KEY") || ""
  };
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
 * Upsert user registration profile into Supabase
 */
function upsertUserProfileGAS(email, nickname, provider) {
  var config = getSupabaseConfig();
  if (!config.key) {
    return { status: 'success', message: 'Local mode bypass.' };
  }
  
  var payload = {
    email: email,
    nickname: nickname,
    auth_provider: provider || 'google',
    last_login: new Date().toISOString()
  };
  
  var headers = {
    "apikey": config.key,
    "Authorization": "Bearer " + config.key,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates" // Upsert behavior on unique constraint (email)
  };
  
  try {
    var res = UrlFetchApp.fetch(config.url + "/rest/v1/users_profile", {
      method: "POST", // PostgREST handles upsert with POST + Prefer header
      headers: headers,
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    if (res.getResponseCode() === 201 || res.getResponseCode() === 200) {
      return { status: 'success', data: res.getContentText() };
    } else {
      return { status: 'error', message: res.getContentText() };
    }
  } catch (err) {
    return { status: 'error', message: err.toString() };
  }
}

/**
 * Fetch data for citizen recommendations and official heritages
 */
function getInitialWebAppData() {
  var config = getSupabaseConfig();
  var result = { official: [], citizen: [], courses: [] };
  
  if (!config.key) {
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

    var resCourses = UrlFetchApp.fetch(config.url + "/rest/v1/courses?select=*&order=created_at.desc", {
      method: "GET",
      headers: headers,
      muteHttpExceptions: true
    });
    if (resCourses.getResponseCode() === 200) {
      result.courses = JSON.parse(resCourses.getContentText());
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
    return { status: "error", message: "Supabase configuration key is missing." };
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
    return stats;
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

/**
 * Insert new official heritage item into database
 */
function insertOfficialHeritageGAS(item) {
  var config = getSupabaseConfig();
  if (!config.key) {
    return { status: "error", message: "Supabase configuration key is missing." };
  }
  
  try {
    var headers = {
      "apikey": config.key,
      "Authorization": "Bearer " + config.key,
      "Content-Type": "application/json",
      "Prefer": "return=representation"
    };
    
    var response = UrlFetchApp.fetch(config.url + "/rest/v1/heritages", {
      method: "POST",
      headers: headers,
      payload: JSON.stringify(item),
      muteHttpExceptions: true
    });
    
    var code = response.getResponseCode();
    if (code === 200 || code === 201) {
      return { status: "success", data: JSON.parse(response.getContentText()) };
    } else {
      return { status: "error", message: response.getContentText() };
    }
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}
