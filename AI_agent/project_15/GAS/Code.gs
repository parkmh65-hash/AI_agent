function doGet() {
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('FashionRAG - AI 패션 스타일링 조언기')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Helper function to include HTML/CSS files inside index.html templates.
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
