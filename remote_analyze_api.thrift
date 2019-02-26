exception InvalidOperation {
  1: i32 what,
  2: string why
}

service RemoteAnalyze {
  string getId()
  string check_uploaded_files(1:string file_hashes)
  void analyze(1:string analysisId, 2:binary zip_file)
  string getStatus(1:string analysisId)
  binary getResults(1:string analysisId)
}