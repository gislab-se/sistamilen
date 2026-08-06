library(shiny)
library(bslib)
library(DT)
library(dplyr)
library(ggplot2)
library(leaflet)
library(plotly)
library(readxl)
library(sf)

`%||%` <- function(x, y) if (is.null(x)) y else x

find_project_root <- function() {
  frame_files <- character()
  for (frame in sys.frames()) {
    if (!is.null(frame$ofile) && is.character(frame$ofile)) {
      frame_files <- c(frame_files, frame$ofile)
    }
  }
  frame_files <- frame_files[!is.na(frame_files) & nzchar(frame_files)]
  frame_dirs <- dirname(normalizePath(frame_files, winslash = "/", mustWork = FALSE))
  seeds <- unique(c(normalizePath(getwd(), winslash = "/", mustWork = FALSE), frame_dirs))
  candidates <- unique(normalizePath(
    c(seeds, file.path(seeds, ".."), file.path(seeds, "..", "..")),
    winslash = "/",
    mustWork = FALSE
  ))

  package_name <- file.path("rawdata", "Paketvolymer_2024_Dalarna_kommun.xlsx")
  service_name <- file.path("rawdata", "Servicepunkter_2026_Dalarna.xlsx")
  matches <- candidates[
    file.exists(file.path(candidates, package_name)) &
      file.exists(file.path(candidates, service_name))
  ]

  if (length(matches) == 0) {
    stop("Could not find project root containing rawdata Excel files.", call. = FALSE)
  }

  matches[[1]]
}

project_root <- find_project_root()
package_file <- file.path(project_root, "rawdata", "Paketvolymer_2024_Dalarna_kommun.xlsx")
service_file <- file.path(project_root, "rawdata", "Servicepunkter_2026_Dalarna.xlsx")

base_palette <- c(
  "#276c68", "#b65a2b", "#6a5d9b", "#7a7d2f", "#365f8d", "#8a4f7d",
  "#58724c", "#9b4a44", "#4d6570", "#a37a2c", "#4c6f9e", "#7d6842",
  "#2d7b3f", "#8f5e3b", "#627044", "#9a5766", "#386f8f", "#6f6040"
)

read_package_volumes <- function() {
  read_excel(package_file, skip = 2) |>
    filter(!is.na(Kommun), tolower(Kommun) != "summa") |>
    rename(
      kommun = Kommun,
      paketbrev_tusen = Paketbrev,
      b2c_tusen = B2C,
      c2x_tusen = C2X,
      b2b_tusen = B2B
    ) |>
    mutate(
      across(ends_with("_tusen"), as.numeric),
      total_paket_tusen = paketbrev_tusen + b2c_tusen + c2x_tusen + b2b_tusen
    )
}

read_service_points <- function() {
  service_raw <- read_excel(service_file, sheet = "sp2026")
  names(service_raw) <- gsub("\r\n", "\n", names(service_raw), fixed = TRUE)

  service <- service_raw |>
    rename(
      aktor = `Aktör`,
      ombud = `OMBUD/BENÄMNING`,
      adress_original = ADRESS,
      ort_original = ORT,
      typ_servicepunkt = `Typ av servicepunkt`,
      leveransdagar_per_vecka = `Leveransfrekvens \n(dgr/vecka)`,
      kommuntyp = Kn_typ,
      befolkning_kn = `Befolkning kn`,
      arbetsstallen = Arbetsställen,
      avlamningsstallen_kn = `Totalt antal avlämnings-ställen (kn)`,
      avlamningsstallen_sbb_kn = `Avl.stle SBB (kn)`,
      avlamningsstallen_lbb_kn = `Avl.stle LBB (kn)`,
      klusterstatus = `enskild/\nkluster`
    ) |>
    mutate(
      leveransdagar_per_vecka = as.numeric(leveransdagar_per_vecka),
      e = as.numeric(e),
      n = as.numeric(n),
      kommun = as.character(kommun),
      aktor = as.character(aktor),
      typ_servicepunkt = as.character(typ_servicepunkt),
      kommuntyp = as.character(kommuntyp),
      klusterstatus = as.character(klusterstatus)
    )

  geo_rows <- which(!is.na(service$e) & !is.na(service$n))
  service$lon <- NA_real_
  service$lat <- NA_real_

  if (length(geo_rows) > 0) {
    service_sf <- st_as_sf(
      service[geo_rows, ],
      coords = c("e", "n"),
      crs = 3006,
      remove = FALSE
    ) |>
      st_transform(4326)
    coords <- st_coordinates(service_sf)
    service$lon[geo_rows] <- coords[, 1]
    service$lat[geo_rows] <- coords[, 2]
  }

  service
}

pct_rank <- function(x) {
  non_missing <- sum(!is.na(x))
  if (non_missing == 0) {
    return(rep(NA_real_, length(x)))
  }
  rank(x, na.last = "keep", ties.method = "average") / non_missing
}

build_commune_profile <- function(packages, service) {
  service_summary <- service |>
    group_by(kommun) |>
    summarise(
      servicepunkter = n(),
      aktorer = n_distinct(aktor),
      typer_servicepunkt = n_distinct(typ_servicepunkt),
      unika_kluster = n_distinct(kluster_id),
      median_leveransdagar_per_vecka = median(leveransdagar_per_vecka, na.rm = TRUE),
      min_leveransdagar_per_vecka = min(leveransdagar_per_vecka, na.rm = TRUE),
      max_leveransdagar_per_vecka = max(leveransdagar_per_vecka, na.rm = TRUE),
      befolkning_kn = max(befolkning_kn, na.rm = TRUE),
      arbetsstallen = max(arbetsstallen, na.rm = TRUE),
      avlamningsstallen_kn = max(avlamningsstallen_kn, na.rm = TRUE),
      kommuntyp = first(na.omit(kommuntyp)),
      .groups = "drop"
    )

  profile <- packages |>
    left_join(service_summary, by = "kommun") |>
    mutate(
      b2c_tusen_per_servicepunkt = b2c_tusen / servicepunkter,
      total_paket_tusen_per_servicepunkt = total_paket_tusen / servicepunkter,
      servicepunkter_per_10000_inv = servicepunkter / befolkning_kn * 10000,
      servicepunkter_per_1000_arbetsstallen = servicepunkter / arbetsstallen * 1000,
      servicepunkter_per_1000_avlamningsstallen = servicepunkter / avlamningsstallen_kn * 1000,
      b2c_tusen_per_1000_avlamningsstallen = b2c_tusen / avlamningsstallen_kn * 1000,
      preliminar_screeningpoang =
        0.45 * pct_rank(b2c_tusen_per_servicepunkt) +
        0.35 * (1 - pct_rank(servicepunkter_per_10000_inv)) +
        0.20 * (1 - pct_rank(median_leveransdagar_per_vecka)),
      preliminar_screeningrank = rank(
        -preliminar_screeningpoang,
        na.last = "keep",
        ties.method = "min"
      )
    ) |>
    arrange(preliminar_screeningrank)

  profile
}

packages <- read_package_volumes()
service <- read_service_points()
profile <- build_commune_profile(packages, service)

all_kommuner <- sort(unique(service$kommun))
all_aktorer <- sort(unique(service$aktor))
all_typer <- sort(unique(service$typ_servicepunkt))
all_kommuntyper <- sort(unique(service$kommuntyp))
max_rank <- max(profile$preliminar_screeningrank, na.rm = TRUE)

metric_box <- function(title, value, detail) {
  value_box(
    title = title,
    value = value,
    showcase = NULL,
    theme = "light",
    p(detail, class = "metric-detail")
  )
}

ui <- page_sidebar(
  title = "Dalarna: servicepunkter och paketflöden",
  theme = bs_theme(
    version = 5,
    bootswatch = "flatly",
    primary = "#276c68",
    secondary = "#6a5d9b",
    success = "#58724c",
    warning = "#b65a2b",
    danger = "#9b4a44"
  ),
  tags$head(
    tags$style(HTML("
      body, .form-control, .btn, .selectize-input { font-family: 'Segoe UI', Arial, sans-serif; }
      body { background: #f7f8f6; }
      .bslib-sidebar-layout > .main { padding-top: 1rem; }
      .sidebar { border-right: 1px solid #d8ddd7; }
      .card, .bslib-card { border-radius: 8px; border-color: #d8ddd7; box-shadow: none; }
      .metric-detail { margin-bottom: 0; color: #52605d; font-size: 0.84rem; }
      .value-box-title { color: #44514e; }
      .leaflet-container { border-radius: 6px; }
      .dataTables_wrapper { font-size: 0.88rem; }
      .form-label, .control-label { font-weight: 650; color: #2e3b39; }
      .btn { border-radius: 6px; }
      .selectize-input { border-radius: 6px; }
      .nav-tabs .nav-link { color: #2e3b39; }
      .nav-tabs .nav-link.active { color: #1f5d58; font-weight: 650; }
    "))
  ),
  sidebar = sidebar(
    width = 330,
    selectizeInput(
      "kommuner",
      "Kommun",
      choices = all_kommuner,
      selected = all_kommuner,
      multiple = TRUE,
      options = list(plugins = list("remove_button"), placeholder = "Välj kommun")
    ),
    selectizeInput(
      "kommuntyper",
      "Kommuntyp",
      choices = all_kommuntyper,
      selected = all_kommuntyper,
      multiple = TRUE,
      options = list(plugins = list("remove_button"), placeholder = "Välj kommuntyp")
    ),
    selectizeInput(
      "aktorer",
      "Aktör",
      choices = all_aktorer,
      selected = all_aktorer,
      multiple = TRUE,
      options = list(plugins = list("remove_button"), placeholder = "Välj aktör")
    ),
    selectizeInput(
      "typer",
      "Typ av servicepunkt",
      choices = all_typer,
      selected = all_typer,
      multiple = TRUE,
      options = list(plugins = list("remove_button"), placeholder = "Välj typ")
    ),
    sliderInput(
      "min_delivery",
      "Minsta leveransdagar per vecka",
      min = 0,
      max = 7,
      value = 0,
      step = 1
    ),
    sliderInput(
      "max_rank",
      "Högsta screeningrank",
      min = 1,
      max = max_rank,
      value = max_rank,
      step = 1
    ),
    radioButtons(
      "color_by",
      "Kartfärg",
      choices = c("Aktör" = "aktor", "Typ" = "typ_servicepunkt", "Kommuntyp" = "kommuntyp"),
      selected = "aktor"
    ),
    downloadButton("download_service", "Ladda ner servicepunkter"),
    downloadButton("download_profile", "Ladda ner kommunprofil")
  ),
  layout_column_wrap(
    width = 1 / 4,
    uiOutput("metric_servicepoints"),
    uiOutput("metric_municipalities"),
    uiOutput("metric_package_volume"),
    uiOutput("metric_delivery")
  ),
  navset_tab(
    nav_panel(
      "Karta",
      layout_columns(
        col_widths = c(8, 4),
        card(
          full_screen = TRUE,
          card_header("Servicepunkter"),
          leafletOutput("service_map", height = 640)
        ),
        card(
          full_screen = TRUE,
          card_header("Kommuner i urvalet"),
          DTOutput("profile_table_compact")
        )
      )
    ),
    nav_panel(
      "Kommunprofil",
      layout_columns(
        col_widths = c(7, 5),
        card(
          full_screen = TRUE,
          card_header("Efterfrågetryck och servicepunktstäthet"),
          plotlyOutput("risk_scatter", height = 460)
        ),
        card(
          full_screen = TRUE,
          card_header("B2C-volym per servicepunkt"),
          plotlyOutput("pressure_bar", height = 460)
        )
      ),
      card(
        full_screen = TRUE,
        card_header("Kommunvis screening"),
        DTOutput("profile_table")
      )
    ),
    nav_panel(
      "Servicepunkter",
      card(
        full_screen = TRUE,
        card_header("Filtrerade servicepunkter"),
        DTOutput("service_table")
      )
    ),
    nav_panel(
      "Datakällor",
      layout_columns(
        col_widths = c(6, 6),
        card(
          card_header("Rådata"),
          tags$ul(
            tags$li("Paketvolymer 2024 per kommun i Dalarna."),
            tags$li("Servicepunkter 2026 med aktör, typ, leveransfrekvens, kommun och koordinater.")
          )
        ),
        card(
          card_header("Screening"),
          tags$ul(
            tags$li("Paketvolymerna behandlas som tusental enligt källfilens rubrik."),
            tags$li("Servicepunkter räknas som rader i bladet sp2026."),
            tags$li("Koordinaterna tolkas som SWEREF 99 TM och visas som WGS84 i kartan.")
          )
        )
      )
    )
  )
)

server <- function(input, output, session) {
  selected_profile <- reactive({
    req(input$kommuner, input$kommuntyper)
    profile |>
      filter(
        kommun %in% input$kommuner,
        kommuntyp %in% input$kommuntyper,
        preliminar_screeningrank <= input$max_rank
      )
  })

  selected_service <- reactive({
    req(input$kommuner, input$kommuntyper, input$aktorer, input$typer)
    allowed_kommuner <- selected_profile()$kommun
    service |>
      filter(
        kommun %in% allowed_kommuner,
        kommuntyp %in% input$kommuntyper,
        aktor %in% input$aktorer,
        typ_servicepunkt %in% input$typer,
        is.na(leveransdagar_per_vecka) | leveransdagar_per_vecka >= input$min_delivery
      )
  })

  output$metric_servicepoints <- renderUI({
    metric_box(
      "Servicepunkter",
      format(nrow(selected_service()), big.mark = " "),
      "Efter valda filter"
    )
  })

  output$metric_municipalities <- renderUI({
    metric_box(
      "Kommuner",
      format(n_distinct(selected_service()$kommun), big.mark = " "),
      "Med minst en servicepunkt"
    )
  })

  output$metric_package_volume <- renderUI({
    selected_kommuner <- unique(selected_service()$kommun)
    total_volume <- profile |>
      filter(kommun %in% selected_kommuner) |>
      summarise(value = sum(total_paket_tusen, na.rm = TRUE)) |>
      pull(value)
    metric_box(
      "Paketvolym",
      paste0(format(round(total_volume, 0), big.mark = " "), " t"),
      "Total årsvolym i tusental"
    )
  })

  output$metric_delivery <- renderUI({
    delivery <- median(selected_service()$leveransdagar_per_vecka, na.rm = TRUE)
    label <- ifelse(is.finite(delivery), sprintf("%.1f", delivery), "NA")
    metric_box(
      "Medianleverans",
      label,
      "Dagar per vecka"
    )
  })

  output$service_map <- renderLeaflet({
    map_data <- selected_service() |>
      filter(!is.na(lon), !is.na(lat))

    validate(need(nrow(map_data) > 0, "Inga servicepunkter med koordinater matchar filtren."))

    color_var <- input$color_by
    color_values <- map_data[[color_var]]
    pal <- colorFactor(base_palette, domain = sort(unique(color_values)), na.color = "#808080")

    popups <- paste0(
      "<strong>", htmltools::htmlEscape(map_data$ombud), "</strong>",
      "<br>", htmltools::htmlEscape(map_data$aktor),
      "<br>", htmltools::htmlEscape(map_data$typ_servicepunkt),
      "<br>", htmltools::htmlEscape(map_data$adress_original), ", ", htmltools::htmlEscape(map_data$ort_original),
      "<br>Kommun: ", htmltools::htmlEscape(map_data$kommun),
      "<br>Leveransdagar/vecka: ", ifelse(is.na(map_data$leveransdagar_per_vecka), "NA", map_data$leveransdagar_per_vecka),
      "<br>Kluster: ", htmltools::htmlEscape(map_data$klusterstatus)
    )

    leaflet(map_data) |>
      addProviderTiles(providers$CartoDB.Positron) |>
      addCircleMarkers(
        lng = ~lon,
        lat = ~lat,
        radius = 6,
        stroke = TRUE,
        weight = 1,
        color = ~pal(color_values),
        fillOpacity = 0.82,
        popup = popups,
        label = ~ombud
      ) |>
      addLegend(
        position = "bottomright",
        pal = pal,
        values = color_values,
        title = switch(
          color_var,
          aktor = "Aktör",
          typ_servicepunkt = "Typ",
          kommuntyp = "Kommuntyp"
        ),
        opacity = 0.9
      )
  })

  output$risk_scatter <- renderPlotly({
    df <- selected_profile()
    validate(need(nrow(df) > 0, "Inga kommuner matchar filtren."))

    p <- ggplot(
      df,
      aes(
        x = servicepunkter_per_10000_inv,
        y = b2c_tusen_per_servicepunkt,
        size = total_paket_tusen,
        color = kommuntyp,
        text = paste0(
          kommun,
          "<br>B2C/servicepunkt: ", round(b2c_tusen_per_servicepunkt, 2),
          "<br>Servicepunkter/10 000 inv: ", round(servicepunkter_per_10000_inv, 2),
          "<br>Screeningrank: ", preliminar_screeningrank
        )
      )
    ) +
      geom_point(alpha = 0.86) +
      scale_color_manual(values = base_palette) +
      scale_size_continuous(range = c(7, 18), guide = "none") +
      labs(
        x = "Servicepunkter per 10 000 invånare",
        y = "B2C-volym per servicepunkt, tusental",
        color = "Kommuntyp"
      ) +
      theme_minimal(base_size = 12) +
      theme(legend.position = "bottom")

    ggplotly(p, tooltip = "text") |>
      layout(margin = list(l = 64, r = 24, t = 16, b = 70))
  })

  output$pressure_bar <- renderPlotly({
    df <- selected_profile() |>
      arrange(b2c_tusen_per_servicepunkt) |>
      mutate(kommun = factor(kommun, levels = kommun))
    validate(need(nrow(df) > 0, "Inga kommuner matchar filtren."))

    p <- ggplot(
      df,
      aes(
        x = kommun,
        y = b2c_tusen_per_servicepunkt,
        fill = kommuntyp,
        text = paste0(
          kommun,
          "<br>B2C/servicepunkt: ", round(b2c_tusen_per_servicepunkt, 2),
          "<br>Servicepunkter: ", servicepunkter
        )
      )
    ) +
      geom_col(width = 0.7) +
      coord_flip() +
      scale_fill_manual(values = base_palette) +
      labs(x = NULL, y = "B2C-volym per servicepunkt, tusental", fill = "Kommuntyp") +
      theme_minimal(base_size = 12) +
      theme(legend.position = "none")

    ggplotly(p, tooltip = "text") |>
      layout(margin = list(l = 112, r = 24, t = 16, b = 56))
  })

  profile_columns <- c(
    "kommun", "preliminar_screeningrank", "preliminar_screeningpoang",
    "b2c_tusen", "servicepunkter", "b2c_tusen_per_servicepunkt",
    "servicepunkter_per_10000_inv", "median_leveransdagar_per_vecka", "kommuntyp"
  )

  output$profile_table_compact <- renderDT({
    selected_profile() |>
      select(kommun, preliminar_screeningrank, b2c_tusen_per_servicepunkt,
             servicepunkter_per_10000_inv, servicepunkter, kommuntyp) |>
      datatable(
        rownames = FALSE,
        options = list(pageLength = 12, dom = "tip", scrollX = TRUE),
        colnames = c(
          "Kommun", "Rank", "B2C/servicepunkt", "Servicepunkter/10 000 inv",
          "Servicepunkter", "Kommuntyp"
        )
      ) |>
      formatRound(c("b2c_tusen_per_servicepunkt", "servicepunkter_per_10000_inv"), 2)
  })

  output$profile_table <- renderDT({
    selected_profile() |>
      select(all_of(profile_columns)) |>
      datatable(
        rownames = FALSE,
        filter = "top",
        extensions = "Buttons",
        options = list(
          pageLength = 15,
          scrollX = TRUE,
          dom = "Bfrtip",
          buttons = c("copy", "csv", "excel")
        ),
        colnames = c(
          "Kommun", "Rank", "Screeningpoäng", "B2C, tusental", "Servicepunkter",
          "B2C/servicepunkt", "Servicepunkter/10 000 inv", "Medianleverans",
          "Kommuntyp"
        )
      ) |>
      formatRound(
        c(
          "preliminar_screeningpoang", "b2c_tusen", "b2c_tusen_per_servicepunkt",
          "servicepunkter_per_10000_inv", "median_leveransdagar_per_vecka"
        ),
        2
      )
  })

  output$service_table <- renderDT({
    selected_service() |>
      select(
        aktor, ombud, kommun, ort_original, typ_servicepunkt,
        leveransdagar_per_vecka, klusterstatus, kommuntyp
      ) |>
      datatable(
        rownames = FALSE,
        filter = "top",
        extensions = "Buttons",
        options = list(
          pageLength = 20,
          scrollX = TRUE,
          dom = "Bfrtip",
          buttons = c("copy", "csv", "excel")
        ),
        colnames = c(
          "Aktör", "Ombud", "Kommun", "Ort", "Typ", "Leveransdagar/vecka",
          "Klusterstatus", "Kommuntyp"
        )
      )
  })

  output$download_service <- downloadHandler(
    filename = function() paste0("servicepunkter_filtrerade_", Sys.Date(), ".csv"),
    content = function(file) {
      write.csv(selected_service(), file, row.names = FALSE, fileEncoding = "UTF-8")
    }
  )

  output$download_profile <- downloadHandler(
    filename = function() paste0("kommunprofil_filtrerad_", Sys.Date(), ".csv"),
    content = function(file) {
      write.csv(selected_profile(), file, row.names = FALSE, fileEncoding = "UTF-8")
    }
  )
}

shinyApp(ui, server)
