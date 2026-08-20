test_files <- c(
  "tests/test_excel_contract.R"
)

for (test_file in test_files) {
  cat("Running", test_file, "\n")
  result <- system2("Rscript", test_file)
  if (!identical(result, 0L)) {
    stop("Test failed: ", test_file, call. = FALSE)
  }
}

cat("All tests passed.\n")
