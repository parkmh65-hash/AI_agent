function doGet() {
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('LangGraph AI 에이전트(요리 레시피)')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Helper function to include HTML/CSS files inside index.html templates.
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
