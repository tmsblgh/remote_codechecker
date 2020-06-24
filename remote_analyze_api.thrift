exception InvalidOperation {
  1: i32 what,
  2: string why
}

service RemoteAnalyze {
  string getId()
  list<string> checkUploadedFiles(1:list<string> fileHashes)
  void analyze(1:string analysisId, 2:binary zipFile)
  string getStatus(1:string analysisId)
  binary getResults(1:string analysisId)
}