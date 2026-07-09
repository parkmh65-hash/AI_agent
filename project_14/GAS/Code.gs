function doGet() {
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('멀티모달 데이터 RAG 시스템')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Helper function to include HTML/CSS files inside index.html templates.
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
