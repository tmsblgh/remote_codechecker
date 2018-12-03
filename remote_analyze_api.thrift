exception InvalidOperation {
  1: i32 what,
  2: string why
}

service RemoteAnalyze {
   binary analyze(1:string command, 2:binary zip_file)
}