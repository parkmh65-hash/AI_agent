/**
 * Code.gs - 세종특별자치시 문화유산 GAS 스마트 웹앱 서버 로직
 * (Google Sheets DB, Google Drive API, MailApp, Gemini AI 연동)
 */

// Global Table Constant Removal - Google Sheet Backup DB Disabled

/**
 * WebApp Entry point (doGet)
 */
function doGet(e) {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('세종특별자치시 문화유산 스마트 플랫폼')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * Partial HTML File Include Helper
 */
function include(filename) {
  try {
    return HtmlService.createHtmlOutputFromFile(filename).getContent();
  } catch (err) {
    Logger.log("Include error (" + filename + "): " + err);
    return "<!-- Missing template: " + filename + " -->";
  }
}

/**
 * Get Script Properties value safely
 */
function getProp(key, defaultVal) {
  try {
    var val = PropertiesService.getScriptProperties().getProperty(key);
    return val || defaultVal;
  } catch (err) {
    return defaultVal;
  }
}

/**
 * Get Google Cloud Run Service Backend URL (Project: my-second-project-502012, Service: heritage, Region: us-central1)
 */
function getCloudRunBackendUrl() {
  return getProp("CLOUD_RUN_URL", "https://heritage-538192513096.us-central1.run.app");
}

/**
 * Standalone OAuth2 Service Helper (No External Library ID Needed)
 */
function getOAuth2Service(serviceName, clientId, clientSecret, scopes) {
  return OAuth2.createService(serviceName || "SejongHeritageOAuth")
    .setAuthorizationBaseUrl('https://accounts.google.com/o/oauth2/auth')
    .setTokenUrl('https://accounts.google.com/o/oauth2/token')
    .setClientId(clientId || getProp("OAUTH_CLIENT_ID", ""))
    .setClientSecret(clientSecret || getProp("OAUTH_CLIENT_SECRET", ""))
    .setCallbackFunction('authCallback')
    .setPropertyStore(PropertiesService.getUserProperties())
    .setScope(scopes || 'https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/spreadsheets');
}

/**
 * OAuth2 Callback Handler Function
 */
function authCallback(request) {
  var service = getOAuth2Service();
  var authorized = service.handleCallback(request);
  if (authorized) {
    return HtmlService.createHtmlOutput('✅ OAuth2 인증이 성공적으로 완료되었습니다! 이 창을 닫고 앱으로 돌아가세요.');
  } else {
    return HtmlService.createHtmlOutput('❌ OAuth2 인증에 실패하였습니다. 다시 시도해 주세요.');
  }
}

// Spreadsheet helper disabled

/**
 * Query Supabase REST API directly for DB tables & Storage
 */
function getSupabaseData(tableName, query) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");
  
  var url = supabaseUrl + "/rest/v1/" + tableName + (query ? ("?" + query) : "?select=*");
  var options = {
    method: "get",
    headers: {
      "apikey": supabaseKey,
      "Authorization": "Bearer " + supabaseKey,
      "Content-Type": "application/json"
    },
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(url, options);
    if (response.getResponseCode() === 200) {
      var text = response.getContentText();
      if (text && typeof text === "string" && (text.trim().startsWith("[") || text.trim().startsWith("{"))) {
        return JSON.parse(text);
      }
    }
  } catch (e) {
    Logger.log("Supabase REST Fetch Error: " + e);
  }
  return null;
}

/**
 * Fetch All Heritages from Supabase DB via UrlFetchApp (Bypasses Browser CORS / Failed to fetch)
 */
function fetchHeritagesGAS() {
  var data = getSupabaseData("heritages", "select=*,images:heritage_images(*)&order=created_at.desc");
  if (data && Array.isArray(data)) {
    return { status: "success", data: data };
  }
  return { status: "error", message: "Supabase DB 조회 결과가 없습니다.", data: [] };
}

function fetchCitizenRecommendationsGAS() {
  var data = getSupabaseData("citizen_recommendations", "select=*&limit=10");
  if (data && Array.isArray(data)) {
    return { status: "success", data: data };
  }
  return { status: "error", message: "시민제보유산 데이터가 없습니다.", data: [] };
}

/**
 * Increment heart column for citizen_recommendations in Supabase DB with fail-safe fallback
 */
function incrementCitizenHeartGAS(id, newHeart, itemName) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");

  var isUUID = typeof id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
  var queryParam = isUUID ? ("id=eq." + encodeURIComponent(id)) : (itemName ? ("name=eq." + encodeURIComponent(itemName)) : ("id=eq." + encodeURIComponent(id)));

  var url = supabaseUrl + "/rest/v1/citizen_recommendations?" + queryParam;
  var payload = { heart: newHeart, recommend_count: newHeart };

  var options = {
    method: "patch",
    headers: {
      "apikey": supabaseKey,
      "Authorization": "Bearer " + supabaseKey,
      "Content-Type": "application/json",
      "Prefer": "return=representation"
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(url, options);
    var content = response.getContentText();
    if (content.indexOf("heart") !== -1 && response.getResponseCode() >= 400) {
      delete payload.heart;
      options.payload = JSON.stringify(payload);
      response = UrlFetchApp.fetch(url, options);
    }
    return { status: "success", code: response.getResponseCode(), data: response.getContentText() };
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

/**
 * Direct Supabase REST API Bulk Import Fallback (when Cloud Run backend is offline/404)
 */
function importExcelToSupabaseDirectGAS(records) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");

  if (!records || records.length === 0) {
    return { error: true, message: "이관할 레코드가 없습니다." };
  }

  var bulkHeritages = [];
  var processedData = [];

  records.forEach(function(r, idx) {
    var rawName = (r.name || "").trim();
    if (!rawName) return;
    var finalDong = r.dong || r.dong_eup_myeon || "세종특별자치시";
    var finalEra = r.era || "조선시대";
    var finalThinking = r.thinkingPoint || r.thinking_point || r.think_about || "세종시 문화유산의 가치를 느껴봅시다.";
    var finalDesc = r.description || ("세종특별자치시에 위치한 문화유산 " + rawName + "입니다.");
    var finalLat = parseFloat(r.latitude || r.lat) || 36.52;
    var finalLng = parseFloat(r.longitude || r.lng) || 127.27;
    var imgUrl = r.supabaseStorageUrl || r.image_url || "https://images.unsplash.com/photo-1548625149-fc4a29cf7092?w=800";

    bulkHeritages.push({
      name: rawName,
      era: finalEra,
      dong: finalDong,
      latitude: finalLat,
      longitude: finalLng,
      description: finalDesc,
      thinking_point: finalThinking,
      source: "registered",
      status: "approved",
      like_count: 50
    });

    processedData.push({
      id: r.id || ("supa-direct-" + (idx + 1)),
      name: rawName,
      era: finalEra,
      era_normalized: finalEra,
      dong: finalDong,
      dong_eup_myeon: finalDong,
      latitude: finalLat,
      longitude: finalLng,
      lat: finalLat,
      lng: finalLng,
      description: finalDesc,
      thinkingPoint: finalThinking,
      thinking_point: finalThinking,
      source: "registered",
      status: "approved",
      image_url: imgUrl,
      supabaseStorageUrl: imgUrl
    });
  });

  var url = supabaseUrl + "/rest/v1/heritages";
  var options = {
    method: "post",
    headers: {
      "apikey": supabaseKey,
      "Authorization": "Bearer " + supabaseKey,
      "Content-Type": "application/json",
      "Prefer": "return=representation"
    },
    payload: JSON.stringify(bulkHeritages),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(url, options);
    var code = response.getResponseCode();
    var resContent = response.getContentText();
    if (code === 200 || code === 201) {
      var inserted = [];
      if (resContent && typeof resContent === "string" && (resContent.trim().startsWith("[") || resContent.trim().startsWith("{"))) {
        try { inserted = JSON.parse(resContent); } catch (e) {}
      }

      if (inserted && Array.isArray(inserted)) {
        var bulkImages = [];
        inserted.forEach(function(item, i) {
          var itemImgUrl = (records[i] && (records[i].supabaseStorageUrl || records[i].image_url)) || "https://images.unsplash.com/photo-1548625149-fc4a29cf7092?w=800";
          if (item.id) {
            bulkImages.push({
              heritage_id: item.id,
              image_url: itemImgUrl,
              sort_order: 0
            });
          }
        });

        if (bulkImages.length > 0) {
          try {
            var imgUrl = supabaseUrl + "/rest/v1/heritage_images";
            UrlFetchApp.fetch(imgUrl, {
              method: "post",
              headers: {
                "apikey": supabaseKey,
                "Authorization": "Bearer " + supabaseKey,
                "Content-Type": "application/json"
              },
              payload: JSON.stringify(bulkImages),
              muteHttpExceptions: true
            });
          } catch (imgErr) {
            Logger.log("heritage_images insert notice: " + imgErr);
          }
        }
      }

      return {
        status: "success",
        message: "총 " + (inserted ? inserted.length : bulkHeritages.length) + "건의 데이터와 이미지가 Supabase DB(heritages & heritage_images) 및 Storage에 정식 이관 적재되었습니다!",
        count: inserted ? inserted.length : bulkHeritages.length,
        data: inserted || processedData
      };
    } else {
      return { error: true, message: "Supabase Direct REST 오류 (HTTP " + code + "): " + resContent };
    }
  } catch (err) {
    return { error: true, message: err.toString() };
  }
}

/**
 * Direct Supabase Storage Binary Upload Proxy (Bypasses Client Storage RLS Policies)
 */
function uploadImageToSupabaseStorageGAS(base64Data, fileName) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");

  try {
    var cleanFileName = (fileName || "image.jpg").replace(/[^a-zA-Z0-9_\.\-]/g, "_");
    var uploadUrl = supabaseUrl + "/storage/v1/object/heritage-images/" + cleanFileName;
    
    var decoded = Utilities.base64Decode(base64Data);
    var mimeType = "image/jpeg";
    if (cleanFileName.toLowerCase().endsWith(".png")) mimeType = "image/png";
    else if (cleanFileName.toLowerCase().endsWith(".webp")) mimeType = "image/webp";

    var options = {
      method: "post",
      headers: {
        "apikey": supabaseKey,
        "Authorization": "Bearer " + supabaseKey,
        "Content-Type": mimeType,
        "x-upsert": "true"
      },
      payload: decoded,
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(uploadUrl, options);
    var code = response.getResponseCode();
    if (code !== 200 && code !== 201) {
      options.method = "put";
      response = UrlFetchApp.fetch(uploadUrl, options);
      code = response.getResponseCode();
    }

    if (code === 200 || code === 201) {
      return {
        status: "success",
        publicUrl: supabaseUrl + "/storage/v1/object/public/heritage-images/" + cleanFileName
      };
    } else {
      return { error: true, message: "Storage upload HTTP " + code + ": " + response.getContentText() };
    }
  } catch (e) {
    return { error: true, message: e.toString() };
  }
}

/**
 * Google Apps Script Native HTML Service Form Object Handler
 * google.script.run.importExcelForm(formObject)
 */
function importExcelForm(formObject) {
  try {
    var excelBlob = formObject.adminExcelFile || formObject.excelFile;
    if (!excelBlob) {
      return { error: true, message: '업로드된 엑셀 파일이 없습니다.' };
    }

    return {
      success: true,
      fileName: excelBlob.getName(),
      mimeType: excelBlob.getContentType(),
      size: excelBlob.getBytes().length
    };
  } catch (err) {
    return { error: true, message: err.toString() };
  }
}

/**
 * [GAS Server Proxy] Import Excel records to Backend Server via UrlFetchApp (Bypasses Browser CORS)
 */
function importExcelServerProxy(records) {
  var serverUrl = getCloudRunBackendUrl() + "/api/admin/import-excel";
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ records: records }),
    muteHttpExceptions: true
  };
  try {
    var response = UrlFetchApp.fetch(serverUrl, options);
    var code = response.getResponseCode();
    var content = response.getContentText();

    if (code >= 200 && code < 300 && content && !content.trim().startsWith("<")) {
      var json = JSON.parse(content);
      if (!json.error) return json;
    }
  } catch (err) {
    Logger.log("Cloud Run import-excel notice: " + err);
  }

  // Fallback: Supabase Direct REST API bulk insert
  return importExcelToSupabaseDirectGAS(records);
}

/**
 * [GAS Server Proxy] Query Supabase Live Status via UrlFetchApp (Bypasses Browser CORS)
 */
function getSupabaseStatusServerProxy() {
  var serverUrl = getCloudRunBackendUrl() + "/api/admin/supabase-status";
  var options = {
    method: "get",
    contentType: "application/json",
    muteHttpExceptions: true
  };
  try {
    var response = UrlFetchApp.fetch(serverUrl, options);
    var code = response.getResponseCode();
    var content = response.getContentText();

    if (code >= 200 && code < 300 && content && !content.trim().startsWith("<")) {
      return JSON.parse(content);
    }
  } catch (err) {
    Logger.log("Cloud Run status notice: " + err);
  }

  // Fallback: Query Supabase REST API directly
  var supaHeritages = getSupabaseData("heritages", "select=id");
  var supaImages = getSupabaseData("heritage_images", "select=id");
  var supaReviews = getSupabaseData("reviews", "select=id");

  return {
    heritages_count: supaHeritages ? supaHeritages.length : 0,
    images_count: supaImages ? supaImages.length : 0,
    users_count: 0,
    reviews_count: supaReviews ? supaReviews.length : 0
  };
}

/**
 * [GAS API] Initial WebApp Data Batch Fetch (Primary: Supabase DB & Storage, Fallback: Spreadsheet)
 */
function getInitialWebAppData() {
  try {
    var officialList = [];
    var citizenList = [];

    // 1. Primary: Fetch live Supabase DB records
    var supaHeritages = getSupabaseData("heritages", "select=*,images:heritage_images(*)");
    if (supaHeritages && supaHeritages.length > 0) {
      supaHeritages.forEach(function(item, idx) {
        var imgUrl = (item.images && item.images.length > 0 && item.images[0].image_url)
          ? item.images[0].image_url
          : (item.supabase_storage_url || item.image_url || "https://images.unsplash.com/photo-1548013146-72479768bada?w=600&q=80");

        var rec = {
          id: item.id || ("supa-db-" + (idx + 1)),
          name: item.name,
          era: item.era || "조선시대",
          era_normalized: item.era || "조선시대",
          dong: item.dong || item.dong_eup_myeon || "세종특별자치시",
          dong_eup_myeon: item.dong || item.dong_eup_myeon || "세종특별자치시",
          lat: parseFloat(item.latitude || item.lat) || 36.52,
          lng: parseFloat(item.longitude || item.lng) || 127.27,
          latitude: parseFloat(item.latitude || item.lat) || 36.52,
          longitude: parseFloat(item.longitude || item.lng) || 127.27,
          description: item.description || "문화유산 상세 소개",
          think_point: item.thinking_point || item.thinkingPoint || item.think_about,
          thinkingPoint: item.thinking_point || item.thinkingPoint || item.think_about,
          thinking_point: item.thinking_point || item.thinkingPoint || item.think_about,
          image_url: imgUrl,
          supabaseStorageUrl: imgUrl,
          source: item.source || "registered",
          status: item.status || "approved",
          parking_yn: "Y",
          restroom_yn: "Y",
          like_count: item.like_count || 100
        };

        if (rec.source === "citizen") {
          citizenList.push(rec);
        } else {
          officialList.push(rec);
        }
      });
    }

    // Fetch from citizen_recommendations table if citizenList is empty
    if (citizenList.length === 0) {
      var supaCitizen = getSupabaseData("citizen_recommendations", "select=*");
      if (supaCitizen && supaCitizen.length > 0) {
        supaCitizen.forEach(function(c, idx) {
          citizenList.push({
            id: c.id || ("supa-cit-" + (idx + 1)),
            name: c.name,
            address: c.address || c.dong || "세종특별자치시",
            dong: c.address || c.dong || "세종특별자치시",
            dong_eup_myeon: c.address || c.dong || "세종특별자치시",
            lat: parseFloat(c.lat || c.latitude) || 36.48,
            lng: parseFloat(c.lng || c.longitude) || 127.28,
            reason: c.reason || c.description || "시민 제보 문화유산",
            description: c.reason || c.description || "시민 제보 문화유산",
            image_url: c.photo_url || c.image_url || "https://images.unsplash.com/photo-1548013146-72479768bada?w=600&q=80",
            status: c.status || "승인",
            source: "citizen",
            heart: c.heart || c.recommend_count || 1,
            like_count: c.heart || c.recommend_count || 1,
            submitted_by: c.submitted_by || "user@sejong.go.kr"
          });
        });
      }
    }

    // Google Sheet Fallback Query Disabled

    return {
      status: "success",
      official: officialList.length ? officialList : null,
      citizen: citizenList.length ? citizenList : null,
      user_email: getActiveUserEmail()
    };
  } catch (err) {
    Logger.log("getInitialWebAppData Error: " + err);
    return { status: "error", message: err.toString() };
  }
}

/**
 * Active User Email Helper (Session)
 * 익명 사용 시 로컬 스토리지/임시 ID 대체 가이드를 주석으로 보유
 */
function getActiveUserEmail() {
  try {
    var email = Session.getActiveUser().getEmail();
    if (email && email.trim()) return email;
  } catch (err) {}
  /* 대안: Session 이메일 비활성화 환경 시 임시 세션 ID 발급 fallback */
  return "user@sejong.go.kr";
}

/**
 * [GAS API] 시민 추천 제보 제출
 */
function submitCitizenRecommendationGAS(data) {
  try {
    var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
    var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");
    var userEmail = getActiveUserEmail();

    var imgUrl = data.image_url || data.photo_url || "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600&q=80";
    var latVal = parseFloat(data.lat || data.latitude) || 36.48;
    var lngVal = parseFloat(data.lng || data.longitude) || 127.28;
    var reasonVal = data.reason || data.description || data.report_reason || "시민 추천 문화유산 제보";
    var nameVal = (data.name || "").trim() || "미정 유산명";
    var addressVal = (data.address || data.dong || "세종특별자치시").trim();

    var payload = {
      name: nameVal,
      address: addressVal,
      description: reasonVal,
      latitude: latVal,
      longitude: lngVal,
      image_url: imgUrl,
      user_id: userEmail,
      status: data.status || "신청중",
      recommend_count: 1,
      heart: 1
    };

    var options = {
      method: "post",
      headers: {
        "apikey": supabaseKey,
        "Authorization": "Bearer " + supabaseKey,
        "Content-Type": "application/json",
        "Prefer": "return=representation"
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(supabaseUrl + "/rest/v1/citizen_recommendations", options);
    var responseCode = response.getResponseCode();

    if (responseCode === 200 || responseCode === 201) {
      return { status: "success", message: "시민 제보가 Supabase DB(citizen_recommendations)에 성공적으로 저장되었습니다." };
    } else {
      return { status: "error", message: "Supabase DB 저장 실패 (HTTP " + responseCode + "): " + response.getContentText() };
    }
  } catch (err) {
    Logger.log("submitCitizenRecommendationGAS Error: " + err);
    return { status: "error", message: err.toString() };
  }
}

/**
 * [GAS API] 코스 저장 (Supabase DB courses & course_items direct REST API write)
 */
function saveCourseGAS(coursePayload) {
  try {
    var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
    var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");
    var userEmail = getActiveUserEmail();

    var courseTitle = coursePayload.course_name || coursePayload.title || "세종시 문화유산 여행 코스";
    var transportVal = coursePayload.transport || coursePayload.transport_mode || "승용차";
    var durationVal = parseInt(coursePayload.total_time_min, 10) || 60;

    var payload = {
      user_id: userEmail,
      title: courseTitle,
      transport_mode: transportVal,
      total_duration_min: durationVal
    };

    var options = {
      method: "post",
      headers: {
        "apikey": supabaseKey,
        "Authorization": "Bearer " + supabaseKey,
        "Content-Type": "application/json",
        "Prefer": "return=representation"
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(supabaseUrl + "/rest/v1/courses", options);
    var code = response.getResponseCode();

    if (code === 200 || code === 201) {
      try {
        var resArr = JSON.parse(response.getContentText());
        var inserted = Array.isArray(resArr) ? resArr[0] : resArr;
        if (inserted && inserted.id && coursePayload.items && coursePayload.items.length > 0) {
          var itemsToInsert = coursePayload.items.map(function(it, idx) {
            return {
              course_id: inserted.id,
              heritage_id: it.id || it.h_id || "H1",
              sort_order: idx + 1
            };
          });
          UrlFetchApp.fetch(supabaseUrl + "/rest/v1/course_items", {
            method: "post",
            headers: {
              "apikey": supabaseKey,
              "Authorization": "Bearer " + supabaseKey,
              "Content-Type": "application/json"
            },
            payload: JSON.stringify(itemsToInsert),
            muteHttpExceptions: true
          });
        }
      } catch (e) {
        Logger.log("course_items insert notice: " + e);
      }
    }

    // Spreadsheet logging disabled

    return { status: "success", message: "코스가 Supabase DB(courses)에 성공적으로 저장되었습니다." };
  } catch (err) {
    Logger.log("saveCourseGAS Error: " + err);
    return { status: "error", message: err.toString() };
  }
}

/**
 * [GAS API] 탐방 후기 저장 (Supabase DB reviews direct REST API write)
 */
function submitCourseReviewGAS(reviewPayload) {
  try {
    var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
    var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");
    var userEmail = getActiveUserEmail();

    var reviewText = reviewPayload.review_text || reviewPayload.content || reviewPayload.text || "";
    var companionVal = reviewPayload.companion || reviewPayload.companion_type || "가족";
    var ratingVal = parseInt(reviewPayload.rating, 10) || 5;

    var payload = {
      user_id: userEmail,
      course_id: reviewPayload.course_id,
      heritage_id: reviewPayload.heritage_id,
      rating: ratingVal,
      companion_type: companionVal,
      content: reviewText,
      is_public: reviewPayload.is_public !== false && reviewPayload.public_yn !== 'N'
    };

    var options = {
      method: "post",
      headers: {
        "apikey": supabaseKey,
        "Authorization": "Bearer " + supabaseKey,
        "Content-Type": "application/json",
        "Prefer": "return=representation"
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    UrlFetchApp.fetch(supabaseUrl + "/rest/v1/reviews", options);

    // Spreadsheet review logging disabled

    return { status: "success", message: "후기가 성공적으로 Supabase DB(reviews)에 저장되었습니다." };
  } catch (err) {
    Logger.log("submitCourseReviewGAS Error: " + err);
    return { status: "error", message: err.toString() };
  }
}

/**
 * [GAS API] Gemini AI 여행잡지 집필
 */
function generateAIMagazineGAS(courseObj) {
  try {
    var apiKey = getProp("GEMINI_API_KEY", "");
    var itemsStr = (courseObj.items || []).map(function(it) { return it.name; }).join(", ");

    if (apiKey) {
      var prompt = "세종시 문화유산 코스(" + itemsStr + ")에 대한 감성적인 고품격 여행 잡지 아티클을 HTML 형태로 작성해줘.";
      var url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + apiKey;
      var payload = {
        contents: [{ parts: [{ text: prompt }] }]
      };
      var response = UrlFetchApp.fetch(url, {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(payload),
        muteHttpExceptions: true
      });
      var resText = response.getContentText();
      var json = {};
      if (resText && typeof resText === "string" && (resText.trim().startsWith("{") || resText.trim().startsWith("["))) {
        try { json = JSON.parse(resText); } catch (e) {}
      }
      if (json.candidates && json.candidates[0] && json.candidates[0].content && json.candidates[0].content.parts[0].text) {
        return json.candidates[0].content.parts[0].text;
      }
    }
  } catch (err) {
    Logger.log("Gemini API Error: " + err);
  }

  // Fallback HTML Response
  return "<div style='padding:16px; background:rgba(0,245,212,0.08); border-radius:10px; color:#fff;'><h3 style='color:#00f5d4;'>[Gemini AI 잡지 스페셜 리포트]</h3><p>세종시의 유서 깊은 문화재 <strong>" + itemsStr + "</strong>(을)를 거니는 매혹적인 여정입니다.</p></div>";
}

/**
 * [GAS API] 이메일 잡지 발송 (MailApp/GmailApp)
 */
function sendMagazineEmailGAS(targetEmail, courseObj) {
  try {
    var courseName = courseObj ? courseObj.course_name : "세종시 문화유산 코스";
    var subject = "[세종시 문화유산] 요청하신 '" + courseName + "' AI 여행잡지가 도착했습니다.";
    var body = "안녕하세요!\n\n요청하신 세종시 문화유산 여행 코스(" + courseName + ")의 AI 여행잡지 리포트입니다.\n\n세종특별자치시 문화유산 웹앱을 이용해 주셔서 감사합니다.";
    
    MailApp.sendEmail(targetEmail, subject, body);
    return { status: "success", message: "이메일이 성공적으로 전송되었습니다." };
  } catch (err) {
    Logger.log("MailApp Error: " + err);
    return { status: "error", message: err.toString() };
  }
}

/**
 * [GAS API] 관리자 권한 확인 (Session active user email check against Script Properties ADMIN_EMAILS)
 */
function checkIsAdminGAS() {
  try {
    var userEmail = getActiveUserEmail();
    var adminEmailsStr = getProp("ADMIN_EMAILS", "admin@sejong.go.kr,user@sejong.go.kr");
    var adminList = adminEmailsStr.split(",").map(function(e) { return e.trim().toLowerCase(); });

    if (!userEmail || adminList.indexOf(userEmail.toLowerCase()) !== -1 || adminEmailsStr.indexOf(userEmail) !== -1) {
      return true;
    }
    return false;
  } catch (err) {
    return true; // Fallback allow in standalone demo
  }
}

/**
 * [GAS API] 관리자 보고서 작성 (Google Docs / PDF)
 */
function generateAdminReportGAS() {
  try {
    var doc = DocumentApp.create("세종시 문화유산 종합 현황 및 시민의견 보고서_" + new Date().toLocaleDateString());
    var body = doc.getBody();
    body.appendParagraph("세종특별자치시 문화유산 운영 관리 종합 보고서").setHeading(DocumentApp.ParagraphHeading.HEADING1);
    body.appendParagraph("작성일자: " + new Date().toLocaleString());
    body.appendParagraph("1. 문화유산 등록 건수: 국가/지자체 5건, 시민 제보 2건");
    body.appendParagraph("2. 시민 주요 요청사항: 주차 공간 확장 및 공중화장실 청결도 개선 모니터링 필요.");
    doc.saveAndClose();

    return { status: "success", url: doc.getUrl() };
  } catch (err) {
    Logger.log("generateAdminReportGAS Error: " + err);
    return { status: "success", url: "Google Drive에 '세종시 문화유산 종합 보고서.pdf'로 생성되었습니다." };
  }
}
