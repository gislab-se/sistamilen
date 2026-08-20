library(readxl)

args <- commandArgs(trailingOnly = FALSE)
file_arg <- "--file="
script_arg <- args[startsWith(args, file_arg)]
script_path <- if (length(script_arg) > 0) {
  normalizePath(sub(file_arg, "", script_arg[[1]]), winslash = "/", mustWork = TRUE)
} else {
  normalizePath("tests/test_excel_contract.R", winslash = "/", mustWork = TRUE)
}

project_root <- normalizePath(file.path(dirname(script_path), ".."), winslash = "/", mustWork = TRUE)
package_file <- file.path(project_root, "rawdata", "Paketvolymer_2024_Dalarna_kommun.xlsx")
service_file <- file.path(project_root, "rawdata", "Servicepunkter_2026_Dalarna.xlsx")
derived_file <- file.path(project_root, "derived", "kommun_paket_service_screening.csv")
app_file <- file.path(project_root, "apps", "dalarna_service_shiny", "app.R")

checks <- list()

check <- function(label, ok, detail = NULL) {
  ok <- isTRUE(ok)
  checks[[length(checks) + 1L]] <<- list(label = label, ok = ok, detail = detail)
  prefix <- if (ok) "[OK]" else "[FAIL]"
  cat(prefix, label)
  if (!is.null(detail) && !ok) {
    cat(" - ", detail, sep = "")
  }
  cat("\n")
}

fail <- function(label, detail = NULL) check(label, FALSE, detail)

near <- function(x, y, tolerance = 1e-6) {
  all(abs(x - y) <= tolerance, na.rm = FALSE)
}

normalize_excel_names <- function(x) {
  gsub("\r\n", "\n", x, fixed = TRUE)
}

package_expected_columns <- c("Kommun", "Paketbrev", "B2C", "C2X", "B2B")
service_expected_columns <- c(
  "DB_ID_2026", "id_aktörsfil", "Aktör", "OMBUD/BENÄMNING", "ADRESS",
  "POSTNUMMER", "ORT", "Typ av servicepunkt", "Leveransfrekvens \n(dgr/vecka)",
  "adress", "postnummer", "postort", "uuidadrpl", "n", "e", "kn", "kommun",
  "Kn_typ", "Län", "Befolkning kn", "Arbetsställen",
  "Totalt antal avlämnings-ställen (kn)", "Avl.stle SBB (kn)",
  "Avl.stle LBB (kn)", "enskild/\nkluster", "kluster_id", "antal_rader_i_kluster"
)
profile_expected_columns <- c(
  "kommun", "paketbrev_tusen", "b2c_tusen", "c2x_tusen", "b2b_tusen",
  "total_paket_tusen", "servicepunkter", "b2c_tusen_per_servicepunkt",
  "servicepunkter_per_10000_inv", "preliminar_screeningrank"
)

check("paketfil finns", file.exists(package_file), package_file)
check("servicefil finns", file.exists(service_file), service_file)
check("Shiny-app finns", file.exists(app_file), app_file)

if (!file.exists(package_file) || !file.exists(service_file) || !file.exists(app_file)) {
  quit(status = 1)
}

package_raw <- read_excel(package_file, skip = 2)
package_names <- names(package_raw)
check(
  "paketfil har förväntade kolumner",
  all(package_expected_columns %in% package_names),
  paste(setdiff(package_expected_columns, package_names), collapse = ", ")
)

package_clean <- package_raw[!is.na(package_raw$Kommun), package_expected_columns]
sum_row <- package_clean[tolower(package_clean$Kommun) == "summa", ]
package_municipalities <- package_clean[tolower(package_clean$Kommun) != "summa", ]
numeric_package_cols <- c("Paketbrev", "B2C", "C2X", "B2B")
package_municipalities[numeric_package_cols] <- lapply(
  package_municipalities[numeric_package_cols],
  as.numeric
)
sum_row[numeric_package_cols] <- lapply(sum_row[numeric_package_cols], as.numeric)

check("paketfil innehåller exakt en Summa-rad", nrow(sum_row) == 1L, paste("antal:", nrow(sum_row)))
check(
  "paketfil innehåller 15 kommunrader",
  nrow(package_municipalities) == 15L,
  paste("antal:", nrow(package_municipalities))
)
if (nrow(sum_row) == 1L) {
  expected_sums <- colSums(package_municipalities[numeric_package_cols], na.rm = TRUE)
  actual_sums <- as.numeric(sum_row[1, numeric_package_cols])
  check(
    "paketfilens Summa-rad matchar kommunraderna",
    near(expected_sums, actual_sums, tolerance = 1e-3),
    paste("förväntat", paste(round(expected_sums, 3), collapse = "/"),
          "men fick", paste(round(actual_sums, 3), collapse = "/"))
  )
}
check(
  "paketfilens kommunnamn är unika",
  length(unique(package_municipalities$Kommun)) == nrow(package_municipalities)
)

service_sheets <- excel_sheets(service_file)
check("servicefil har bladet sp2026", "sp2026" %in% service_sheets)
check("servicefil har bladet Kluster", "Kluster" %in% service_sheets)

service_raw <- read_excel(service_file, sheet = "sp2026")
names(service_raw) <- normalize_excel_names(names(service_raw))
service_names <- names(service_raw)
check(
  "servicefil har förväntade kolumner",
  all(service_expected_columns %in% service_names),
  paste(setdiff(service_expected_columns, service_names), collapse = ", ")
)
check("servicefil har 487 servicepunktsrader", nrow(service_raw) == 487L, paste("antal:", nrow(service_raw)))
check("servicefilens DB_ID_2026 är unik", anyDuplicated(service_raw$DB_ID_2026) == 0L)
check("servicefilen saknar inte kommun", !any(is.na(service_raw$kommun)))
check("servicefilen saknar inte aktör", !any(is.na(service_raw$Aktör)))

package_kommuner <- sort(unique(package_municipalities$Kommun))
service_kommuner <- sort(unique(service_raw$kommun))
check(
  "kommunerna matchar mellan paketfil och servicefil",
  identical(package_kommuner, service_kommuner),
  paste(
    "bara paket:", paste(setdiff(package_kommuner, service_kommuner), collapse = ", "),
    "bara service:", paste(setdiff(service_kommuner, package_kommuner), collapse = ", ")
  )
)

service_raw$e <- as.numeric(service_raw$e)
service_raw$n <- as.numeric(service_raw$n)
coord_complete <- !is.na(service_raw$e) & !is.na(service_raw$n)
check(
  "alla servicepunkter har e/n-koordinater",
  all(coord_complete),
  paste("saknar:", sum(!coord_complete))
)
check(
  "e/n-koordinater ligger inom rimligt Dalarna-intervall",
  all(service_raw$e > 350000 & service_raw$e < 650000 & service_raw$n > 6600000 & service_raw$n < 6900000),
  paste("e:", paste(range(service_raw$e, na.rm = TRUE), collapse = "-"),
        "n:", paste(range(service_raw$n, na.rm = TRUE), collapse = "-"))
)

app_env <- new.env(parent = globalenv())
suppressPackageStartupMessages(suppressWarnings(source(app_file, local = app_env)))

check("Shiny-appen läser 15 kommunprofiler", nrow(app_env$profile) == 15L, paste("antal:", nrow(app_env$profile)))
check("Shiny-appen läser 487 servicepunkter", nrow(app_env$service) == 487L, paste("antal:", nrow(app_env$service)))
check(
  "Shiny-appens kommuner matchar Excel-filerna",
  identical(sort(unique(app_env$service$kommun)), package_kommuner)
)
check(
  "Shiny-appens WGS84-longituder/latituder är rimliga",
  all(app_env$service$lon > 10 & app_env$service$lon < 18 &
        app_env$service$lat > 59 & app_env$service$lat < 63, na.rm = TRUE),
  paste("lon:", paste(range(app_env$service$lon, na.rm = TRUE), collapse = "-"),
        "lat:", paste(range(app_env$service$lat, na.rm = TRUE), collapse = "-"))
)

if (file.exists(derived_file)) {
  derived <- read.csv(derived_file, fileEncoding = "UTF-8-BOM", check.names = FALSE)
  check(
    "härledd CSV har förväntade kolumner",
    all(profile_expected_columns %in% names(derived)),
    paste(setdiff(profile_expected_columns, names(derived)), collapse = ", ")
  )
  check("härledd CSV har 15 kommunrader", nrow(derived) == 15L, paste("antal:", nrow(derived)))

  app_profile <- app_env$profile[order(app_env$profile$kommun), profile_expected_columns]
  derived_profile <- derived[order(derived$kommun), profile_expected_columns]
  row.names(app_profile) <- NULL
  row.names(derived_profile) <- NULL

  check(
    "härledd CSV har samma kommuner som Excel",
    identical(sort(derived$kommun), package_kommuner)
  )

  numeric_cols <- setdiff(profile_expected_columns, "kommun")
  numeric_matches <- all(vapply(numeric_cols, function(col) {
    near(as.numeric(app_profile[[col]]), as.numeric(derived_profile[[col]]), tolerance = 1e-6)
  }, logical(1)))
  check(
    "härledd CSV matchar Shiny-appens beräkningar från Excel",
    numeric_matches
  )
} else {
  fail("härledd CSV finns", derived_file)
}

failed <- vapply(checks, function(x) !x$ok, logical(1))
cat("\n")
cat(sum(!failed), "av", length(checks), "kontroller passerade.\n")

if (any(failed)) {
  cat("Misslyckade kontroller:\n")
  for (item in checks[failed]) {
    cat("- ", item$label, "\n", sep = "")
  }
  quit(status = 1)
}

cat("Alla Excel-kontrakt stämmer.\n")
