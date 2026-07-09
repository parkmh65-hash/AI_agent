function doGet() {
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('ChatPDF With Multiquery+HybridSearch+RagFusion')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Helper function to include HTML/CSS files inside index.html templates.
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
