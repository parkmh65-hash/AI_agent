/**
 * Google Apps Script Backend (Code.gs)
 * project_08 - 현진건 작가와 대화하기
 */

function doGet(e) {
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('현진건 작가와 대화하기')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Sends the user question and the optional response_id to the FastAPI backend.
 * 
 * @param {string} question The user question.
 * @param {string} responseId The optional previous response ID for chaining conversation.
 * @return {object} The reply and new response_id from the FastAPI server.
 */
function askAI(question, responseId) {
  var backendUrl = PropertiesService.getScriptProperties().getProperty('BACKEND_URL');
  if (!backendUrl) {
    // Fallback URL for local testing or placeholder
    backendUrl = "http://localhost:8000/chat";
  }
  
  // Auto-append '/chat' if missing
  if (backendUrl && !backendUrl.match(/\/chat\/?$/)) {
    backendUrl = backendUrl.replace(/\/$/, '') + '/chat';
  }
  
  var payload = {
    "message": question,
    "response_id": responseId || null
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
      return JSON.parse(responseBody);
    } else {
      return {
        "reply": "⚠️ 백엔드 서버에서 오류를 반환했습니다 (HTTP " + responseCode + "): " + responseBody,
        "error": true
      };
    }
  } catch (error) {
    return {
      "reply": "❌ 백엔드 서버와 통신할 수 없습니다. 서버 상태 또는 BACKEND_URL 설정을 확인해 주세요.\n(에러: " + error.toString() + ")",
      "error": true
    };
  }
}
