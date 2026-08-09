/**
 * Code.gs - 세종특별자치시 문화유산 GAS 스마트 웹앱 서버 로직
 * (Supabase DB, Google Drive API, MailApp, Gemini AI 연동 백엔드 전용)
 */

function doGet(e) {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('세종특별자치시 문화유산 스마트 플랫폼')
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

function getProp(key, defaultVal) {
  try {
    var val = PropertiesService.getScriptProperties().getProperty(key);
    return val || defaultVal;
  } catch (err) {
    return defaultVal;
  }
}

function getCloudRunBackendUrl() {
  return getProp("CLOUD_RUN_URL", "https://heritage-react-538192513096.us-central1.run.app");
}

function getActiveUserEmail() {
  try {
    var email = Session.getActiveUser().getEmail();
    return email || "user@sejong.go.kr";
  } catch (e) {
    return "user@sejong.go.kr";
  }
}

function getOAuth2Service() {
  return OAuth2.createService("SejongHeritageOAuth")
    .setAuthorizationBaseUrl('https://accounts.google.com/o/oauth2/auth')
    .setTokenUrl('https://accounts.google.com/o/oauth2/token')
    .setClientId(getProp("OAUTH_CLIENT_ID", ""))
    .setClientSecret(getProp("OAUTH_CLIENT_SECRET", ""))
    .setCallbackFunction('authCallback')
    .setPropertyStore(PropertiesService.getUserProperties())
    .setScope('https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/spreadsheets');
}

function authCallback(request) {
  var service = getOAuth2Service();
  var authorized = service.handleCallback(request);
  if (authorized) {
    return HtmlService.createHtmlOutput('✅ OAuth2 인증이 성공적으로 완료되었습니다!');
  } else {
    return HtmlService.createHtmlOutput('❌ OAuth2 인증에 실패하였습니다.');
  }
}

// ----------------------------------------------------
// Supabase REST 연동 공통 유틸리티
// ----------------------------------------------------

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
      return JSON.parse(response.getContentText());
    }
  } catch (err) {
    Logger.log("Supabase GET error: " + err);
  }
  return [];
}

// ----------------------------------------------------
// 클라이언트 호출용 API 엔드포인트
// ----------------------------------------------------

// 1. 초기 데이터 일괄 로드 (문화유산 + 시민 제보 + 사용자 이메일)
function getInitialWebAppData() {
  try {
    var officialList = [];
    var citizenList = [];

    var supaHeritages = getSupabaseData("heritages", "select=*,images:heritage_images(*)");
    if (supaHeritages && supaHeritages.length > 0) {
      supaHeritages.forEach(function(item, idx) {
        var imgUrl = (item.images && item.images.length > 0 && item.images[0].image_url)
          ? item.images[0].image_url
          : (item.supabase_storage_url || item.image_url || "");

        var rec = {
          id: item.id || ("supa-db-" + (idx + 1)),
          name: item.name,
          era: item.era || "시대미상",
          era_normalized: item.era || "시대미상",
          dong: item.dong || item.dong_eup_myeon || "세종시",
          dong_eup_myeon: item.dong || item.dong_eup_myeon || "세종시",
          lat: parseFloat(item.latitude || item.lat) || 36.52,
          lng: parseFloat(item.longitude || item.lng) || 127.27,
          latitude: parseFloat(item.latitude || item.lat) || 36.52,
          longitude: parseFloat(item.longitude || item.lng) || 127.27,
          description: item.description || "상세 설명이 제공되지 않습니다.",
          thinkingPoint: item.thinking_point || item.thinkingPoint || "세종시 문화유산의 가치를 느껴봅시다.",
          thinking_point: item.thinking_point || item.thinkingPoint || "세종시 문화유산의 가치를 느껴봅시다.",
          image_url: imgUrl,
          source: item.source || "registered",
          status: item.status || "approved",
          like_count: item.like_count || 50
        };

        if (rec.source === "citizen") {
          citizenList.push(rec);
        } else {
          officialList.push(rec);
        }
      });
    }

    if (citizenList.length === 0) {
      var supaCitizen = getSupabaseData("citizen_recommendations", "select=*");
      if (supaCitizen && supaCitizen.length > 0) {
        supaCitizen.forEach(function(c, idx) {
          citizenList.push({
            id: c.id || ("supa-cit-" + (idx + 1)),
            name: c.name,
            address: c.address || c.dong || "세종시",
            dong: c.address || c.dong || "세종시",
            dong_eup_myeon: c.address || c.dong || "세종시",
            lat: parseFloat(c.lat || c.latitude) || 36.48,
            lng: parseFloat(c.lng || c.longitude) || 127.28,
            reason: c.reason || c.description || "시민이 제보한 문화유산입니다.",
            description: c.reason || c.description || "시민이 제보한 문화유산입니다.",
            image_url: c.photo_url || c.image_url || "",
            status: c.status || "대기",
            source: "citizen",
            like_count: c.heart || c.recommend_count || 1,
            submitted_by: c.submitted_by || "user@sejong.go.kr"
          });
        });
      }
    }

    return {
      status: "success",
      official: officialList,
      citizen: citizenList,
      user_email: getActiveUserEmail()
    };
  } catch (err) {
    Logger.log("getInitialWebAppData Error: " + err);
    return { status: "error", message: err.toString() };
  }
}

// 2. 시민 제보 좋아요 수 업데이트
function incrementCitizenHeartGAS(id, newHeart, itemName) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");
  
  var isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
  var queryParam = isUUID ? "id=eq." + id : "name=eq." + encodeURIComponent(itemName);

  var options = {
    method: "patch",
    headers: {
      "apikey": supabaseKey,
      "Authorization": "Bearer " + supabaseKey,
      "Content-Type": "application/json"
    },
    payload: JSON.stringify({ heart: newHeart, recommend_count: newHeart }),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(supabaseUrl + "/rest/v1/citizen_recommendations?" + queryParam, options);
    return { status: "success", code: response.getResponseCode() };
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

// 3. 시민 제보 등록
function submitCitizenRecommendationGAS(payload) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");

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

  try {
    var response = UrlFetchApp.fetch(supabaseUrl + "/rest/v1/citizen_recommendations", options);
    var code = response.getResponseCode();
    if (code === 200 || code === 201) {
      return { status: "success", data: JSON.parse(response.getContentText()) };
    }
    return { status: "error", message: "Supabase insert error: " + response.getContentText() };
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

// 4. 탐방 후기 등록
function submitCourseReviewGAS(reviewPayload) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");

  var options = {
    method: "post",
    headers: {
      "apikey": supabaseKey,
      "Authorization": "Bearer " + supabaseKey,
      "Content-Type": "application/json"
    },
    payload: JSON.stringify(reviewPayload),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(supabaseUrl + "/rest/v1/reviews", options);
    return { status: "success", code: response.getResponseCode() };
  } catch (e) {
    return { status: "error", message: e.toString() };
  }
}

// 5. 나만의 코스 저장
function saveCourseGAS(coursePayload) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");
  
  var payload = {
    user_id: getActiveUserEmail(),
    title: coursePayload.title || "세종 문화유산 코스",
    transport_mode: coursePayload.transport_mode || "승용차",
    total_duration_min: parseInt(coursePayload.total_duration_min, 10) || 60
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

  try {
    var response = UrlFetchApp.fetch(supabaseUrl + "/rest/v1/courses", options);
    var code = response.getResponseCode();

    if (code === 200 || code === 201) {
      var inserted = JSON.parse(response.getContentText())[0];
      if (inserted && inserted.id && coursePayload.items && coursePayload.items.length > 0) {
        var itemsToInsert = coursePayload.items.map(function(it, idx) {
          return {
            course_id: inserted.id,
            heritage_id: it.id || "H1",
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
      return { status: "success", data: inserted };
    }
    return { status: "error", message: response.getContentText() };
  } catch (err) {
    return { status: "error", message: err.toString() };
  }
}

// 6. 저장된 코스 목록 조회
function fetchSavedCoursesGAS() {
  return getSupabaseData("courses", "select=*,items:course_items(*)&order=created_at.desc");
}

// 7. 한국관광공사 OpenAPI 조회 프록시
function fetchKorServiceGAS(op, keyword, arrange, areaCode) {
  var serviceKey = 'a574450c4e9b74f08312c1f80520d00e608341fca348bf1cb6bd02ff3584cf14';
  var directUrl = "https://apis.data.go.kr/B551011/KorService2/" + op 
    + "?serviceKey=" + serviceKey 
    + "&MobileOS=ETC&MobileApp=Sejong&_type=json"
    + "&keyword=" + encodeURIComponent(keyword) 
    + "&areaCode=" + (areaCode || "8") 
    + "&numOfRows=20&pageNo=1";

  try {
    var response = UrlFetchApp.fetch(directUrl, { muteHttpExceptions: true });
    if (response.getResponseCode() === 200) {
      return { status: "success", data: JSON.parse(response.getContentText()) };
    }
  } catch (err) {
    Logger.log("fetchKorServiceGAS direct error: " + err);
  }
  return { status: "error", message: "OpenAPI fetch failed" };
}

// 8. Supabase Storage 파일 업로드 프록시
function uploadImageToSupabaseStorageGAS(base64Data, fileName) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");
  
  try {
    var cleanFileName = fileName.replace(/[^a-zA-Z0-9_\.\-]/g, "_");
    var uploadUrl = supabaseUrl + "/storage/v1/object/heritage-images/" + cleanFileName;
    
    var rawData = Utilities.base64Decode(base64Data.split(',')[1] || base64Data);
    var mimeString = base64Data.split(',')[0].split(':')[1].split(';')[0];
    
    var options = {
      method: "post",
      headers: {
        "apikey": supabaseKey,
        "Authorization": "Bearer " + supabaseKey,
        "Content-Type": mimeString,
        "x-upsert": "true"
      },
      payload: rawData,
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(uploadUrl, options);
    if (response.getResponseCode() === 200 || response.getResponseCode() === 201) {
      return {
        status: "success",
        publicUrl: supabaseUrl + "/storage/v1/object/public/heritage-images/" + cleanFileName
      };
    }
    return { status: "error", message: "Storage response: " + response.getContentText() };
  } catch (err) {
    return { status: "error", message: err.toString() };
  }
}

// 9. 관리자 엑셀 일괄 이관 처리
function importExcelToSupabaseDirectGAS(records) {
  var supabaseUrl = getProp("SUPABASE_URL", "https://pdpmtgnagwzcsftavtap.supabase.co");
  var supabaseKey = getProp("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkcG10Z25hZ3d6Y3NmdGF2dGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4NTA4NjYsImV4cCI6MjA5NDQyNjg2Nn0.eA_TDXZ8GRR4HbDCkX5A-rvWPx3Bz_KEyxSev1MF2qM");

  if (!records || records.length === 0) return { error: true, message: "이관할 레코드가 없습니다." };

  var bulkHeritages = records.map(function(r, idx) {
    var rawName = (r.name || "").trim();
    var finalDong = r.dong || r.dong_eup_myeon || "세종시";
    var finalEra = r.era || "조선시대";
    var finalThinking = r.thinkingPoint || r.thinking_point || "세종시 문화유산의 가치를 느껴봅시다.";
    var finalDesc = r.description || ("세종특별자치시에 위치한 문화유산 " + rawName + "입니다.");
    var finalLat = parseFloat(r.latitude || r.lat) || 36.52;
    var finalLng = parseFloat(r.longitude || r.lng) || 127.27;

    return {
      h_id: r.h_id || ("H" + (idx + 1)),
      name: rawName,
      address: r.address || ("세종특별자치시 " + finalDong),
      dong: finalDong,
      era: finalEra,
      era_normalized: r.era_normalized || finalEra,
      latitude: finalLat,
      longitude: finalLng,
      description: finalDesc,
      thinking_point: finalThinking,
      source: "registered",
      status: "approved",
      like_count: 50
    };
  });

  var options = {
    method: "post",
    headers: {
      "apikey": supabaseKey,
      "Authorization": "Bearer " + supabaseKey,
      "Content-Type": "application/json",
      "Prefer": "resolution=merge-duplicates, return=representation"
    },
    payload: JSON.stringify(bulkHeritages),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(supabaseUrl + "/rest/v1/heritages?on_conflict=h_id", options);
    var code = response.getResponseCode();
    if (code === 200 || code === 201) {
      var inserted = JSON.parse(response.getContentText());
      var bulkImages = [];
      inserted.forEach(function(item, idx) {
        var itemImgUrl = records[idx]?.supabaseStorageUrl || records[idx]?.image_url || "";
        if (item.id && itemImgUrl) {
          bulkImages.push({
            heritage_id: item.id,
            image_url: itemImgUrl,
            sort_order: 0
          });
        }
      });
      
      if (bulkImages.length > 0) {
        UrlFetchApp.fetch(supabaseUrl + "/rest/v1/heritage_images", {
          method: "post",
          headers: {
            "apikey": supabaseKey,
            "Authorization": "Bearer " + supabaseKey,
            "Content-Type": "application/json"
          },
          payload: JSON.stringify(bulkImages),
          muteHttpExceptions: true
        });
      }
      return { status: "success", count: inserted.length };
    }
    return { status: "error", message: response.getContentText() };
  } catch (err) {
    return { status: "error", message: err.toString() };
  }
}

// 10. Google Docs 종합 현황 통계 보고서 발행
function generateAdminReportGAS() {
  try {
    var doc = DocumentApp.create("세종특별자치시 문화유산 종합 현황 및 개선사항 통계 보고서");
    var body = doc.getBody();
    
    body.appendParagraph("세종특별자치시 문화유산 종합 관리 통계 보고서")
        .setFontSize(22)
        .setBold(true)
        .setAlignment(DocumentApp.HorizontalAlignment.CENTER);
        
    body.appendParagraph("\n발행일시: " + new Date().toLocaleString())
        .setFontSize(10)
        .setAlignment(DocumentApp.HorizontalAlignment.RIGHT);

    body.appendParagraph("\n1. 서비스 종합 운영 현황")
        .setFontSize(14)
        .setBold(true);
    
    body.appendParagraph("본 보고서는 세종시 문화유산 스마트 플랫폼의 실시간 피드백 및 모니터링 정보를 바탕으로 자동 생성된 문서입니다.\n현재 플랫폼에는 다수의 지정 문화유산 정보 및 시민들이 직접 제보한 문화유산이 등록되어 있으며, 실시간 GIS 이동 경로 피드백 시스템을 통해 수집된 개선 요청 피드백이 집계되어 관리되고 있습니다.");

    doc.saveAndClose();
    return { status: "success", url: doc.getUrl() };
  } catch (err) {
    return { status: "error", message: err.toString() };
  }
}

function checkIsAdminGAS() {
  return true; // Simple administrative access check bypass
}
