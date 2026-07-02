/**
 * Google Apps Script Backend (Code.gs)
 *
 * Serves the HTML UI and handles server-side execution (e.g. proxying RAG requests to Render).
 */

function doGet(e) {
  // Load index.html and evaluate any template variables (e.g., style, script imports)
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('AI Agent Workspace (project_04)')
      // Crucial: ALLOWALL enables embedding the Web App in Google Sites iframe!
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Sends the user question to the FastAPI backend hosted on Render.
 * 
 * @param {string} question The question asked by the user.
 * @return {object} The reply from the AI agent.
 */
function askAI(question) {
  // Fetch the backend URL from script properties (recommended) or fallback
  var backendUrl = PropertiesService.getScriptProperties().getProperty('BACKEND_URL');
  if (!backendUrl || backendUrl === "https://your-render-url.onrender.com/chat") {
    // Fallback URL placeholder
    backendUrl = "https://your-render-url.onrender.com/chat";
    return {
      "reply": "💡 [안내] Google Apps Script 프로젝트 설정(Project Settings) -> Script Properties에 'BACKEND_URL' 키와 실제 배포된 Render 웹 서비스 URL(/chat 포함)을 설정해 주세요.\n\n현재 임시 설정된 URL: " + backendUrl,
      "error": true
    };
  }
  
  // Auto-append '/chat' if missing to avoid routing errors
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
