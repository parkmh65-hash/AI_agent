// OAuth2.gs - ver_02 Apps Script OAuth2 and Authentication helper library stub

function getOAuthService() {
  return {
    hasAccess: function() { return true; },
    getAccessToken: function() { return "mock_access_token"; },
    reset: function() {},
    handleCallback: function(request) { return HtmlService.createHtmlOutput("OAuth success stub"); }
  };
}

function authCallback(request) {
  var service = getOAuthService();
  var authorized = service.handleCallback(request);
  if (authorized) {
    return HtmlService.createHtmlOutput("접속 승인이 완료되었습니다. 이 창을 닫으셔도 좋습니다.");
  } else {
    return HtmlService.createHtmlOutput("접속 승인 실패. 다시 진행해 주세요.");
  }
}
