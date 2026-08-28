function doGet() {
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('다중 에이전트 블로그 작성기')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Helper function to include HTML/CSS templates inside index.html.
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
