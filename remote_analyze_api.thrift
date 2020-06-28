exception AnalysisNotFoundException {
}

exception AnalysisNotCompletedException {
}

service RemoteAnalyze {
  string getId()
  list<string> checkUploadedFiles(1:list<string> fileHashes)
  void analyze(1:string analysisId, 2:binary zipFile)
  string getStatus(1:string analysisId) throws (1:AnalysisNotFoundException notFoundException)
  binary getResults(1:string analysisId) throws (1:AnalysisNotFoundException notFoundException, 2:AnalysisNotCompletedException notCompletedException)
}