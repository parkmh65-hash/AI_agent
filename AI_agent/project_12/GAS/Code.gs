function doGet() {
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle("ChatPDF With Multiquery+HybridSearch+RagFusion")
      .addMetaTag('viewport', 'width=device-width, initial-scale=1')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
