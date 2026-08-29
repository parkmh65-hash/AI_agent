/**
 * Smart Cultural Heritage & Tour Exploration Integrated Platform
 * Google Apps Script (GAS) HTML Service Backend Script
 */

function doGet(e) {
  var htmlOutput = HtmlService.createHtmlOutputFromFile('index')
      .setTitle('스마트 문화유산 & 탐방 통합 플랫폼 | 세종·국가유산')
      .addMetaTag('viewport', 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  return htmlOutput;
}

/**
 * Helper function to include HTML snippet files in GAS
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

/**
 * Server-side API Proxy for Google Apps Script execution
 * Forwards requests to Python FastAPI backend or Supabase PostgREST API
 */
function apiProxy(endpoint, method, payloadJson) {
  var FASTAPI_URL = 'http://localhost:8000'; // Replace with public URL if deployed (e.g. Render/Cloud Run)
  var options = {
    'method': method || 'get',
    'contentType': 'application/json',
    'muteHttpExceptions': true
  };
  
  if (payloadJson) {
    options['payload'] = typeof payloadJson === 'string' ? payloadJson : JSON.stringify(payloadJson);
  }
  
  try {
    var response = UrlFetchApp.fetch(FASTAPI_URL + endpoint, options);
    return response.getContentText();
  } catch (err) {
    return JSON.stringify({
      'status': 'error',
      'message': err.toString()
    });
  }
}
