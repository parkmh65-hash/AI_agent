/**
 * Google Apps Script Backend (Code.gs)
 *
 * Serves the HTML UI and handles server-side execution proxying to the FastAPI backend.
 */

function doGet(e) {
  // Load index.html and evaluate any template variables
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('PDF에게 물어보기')
      // ALLOWALL enables embedding the Web App in Google Sites iframe
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Sends the user question to the FastAPI backend.
 * 
 * @param {string} question The question asked by the user.
 * @return {object} The reply from the AI agent.
 */
function askAI(question) {
  // Fetch the backend URL from script properties (recommended) or fallback
  var backendUrl = PropertiesService.getScriptProperties().getProperty('BACKEND_URL');
  if (!backendUrl || backendUrl === "https://your-render-url.onrender.com/chat") {
    // Fallback placeholder URL warning
    backendUrl = "https://your-render-url.onrender.com/chat";
    return {
      "reply": "💡 [안내] Google Apps Script 프로젝트 설정(Settings) -> Script Properties에 'BACKEND_URL' 키와 실제 배포된 Render 웹 서비스 URL(/chat 포함)을 설정해 주세요.\n\n현재 임시 설정된 URL: " + backendUrl,
      "error": true
    };
  }
  
  // Auto-append '/chat' if missing
  if (backendUrl && !backendUrl.match(/\/chat\/?$/)) {
    backendUrl = backendUrl.replace(/\/$/, '') + '/chat';
  }
  
  var payload = {
    "message": question
  };
  
  var options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };
  
  try {
    var response = UrlFetchApp.fetch(backendUrl, options);
    var responseCode = response.getResponseCode();
    var responseBody = response.getContentText();
    
    if (responseCode === 200) {
      var data = JSON.parse(responseBody);
      return data;
    } else {
      return {
        "reply": "⚠️ 백엔드 오류 발생 (HTTP " + responseCode + "):\n" + responseBody,
        "error": true
      };
    }
  } catch (error) {
    return {
      "reply": "❌ 백엔드 서버와 통신할 수 없습니다:\n" + error.toString(),
      "error": true
    };
  }
}

/**
 * Receives Base64-encoded PDF from client, decodes it, 
 * and forwards (posts) it to FastAPI /upload_pdf endpoint.
 * 
 * @param {string} base64Data Base64 string of the PDF file.
 * @param {string} fileName Original name of the PDF file.
 * @return {object} Result JSON containing status details.
 */
function uploadPdfFile(base64Data, fileName) {
  var backendUrl = PropertiesService.getScriptProperties().getProperty('BACKEND_URL');
  if (!backendUrl || backendUrl === "https://your-render-url.onrender.com/chat") {
    return {
      "error": true,
      "message": "💡 [안내] Google Apps Script 프로젝트 설정 -> 스크립트 속성에 'BACKEND_URL'이 설정되지 않았습니다."
    };
  }

  // Point to /upload_pdf endpoint instead of /chat
  var uploadUrl = backendUrl.replace(/\/chat\/?$/, '').replace(/\/$/, '') + '/upload_pdf';

  try {
    // Decode base64 to byte array blob
    var decoded = Utilities.base64Decode(base64Data);
    var blob = Utilities.newBlob(decoded, 'application/pdf', fileName);

    var payload = {
      'file': blob
    };

    var options = {
      'method': 'post',
      'payload': payload,
      'muteHttpExceptions': true
    };

    var response = UrlFetchApp.fetch(uploadUrl, options);
    var responseCode = response.getResponseCode();
    var responseBody = response.getContentText();

    if (responseCode === 200) {
      return JSON.parse(responseBody);
    } else {
      return {
        "error": true,
        "message": "백엔드 서버 에러 (HTTP " + responseCode + "): " + responseBody
      };
    }
  } catch (error) {
    return {
      "error": true,
      "message": "백엔드 서버와 통신 실패: " + error.toString()
    };
  }
}

