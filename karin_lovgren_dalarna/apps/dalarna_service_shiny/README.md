# Dalarna Service Shiny

Lokal Shiny-app för att utforska paketvolymer och servicepunkter i Dalarna.

## Starta

Från projektroten:

```r
shiny::runApp("apps/dalarna_service_shiny", host = "127.0.0.1", port = 3838)
```

Öppna sedan:

<http://127.0.0.1:3838>

## Testa mot Excel-filerna

Från projektroten:

```powershell
Rscript scripts\run_tests.R
```

Testet kontrollerar schema, rader, kommunmatchning, paketfilens summor, koordinater, appens inläsning och att den härledda CSV:n matchar appens beräkningar från Excel-filerna.

## Innehåll

- Interaktiv karta över servicepunkter.
- Filter för kommun, kommuntyp, aktör, servicepunktstyp och leveransfrekvens.
- Kommunvis screening av paketvolym per servicepunkt och servicepunktstäthet.
- Nedladdning av filtrerad servicepunktstabell och kommunprofil.

## Datakällor

Appen läser direkt från:

- `rawdata/Paketvolymer_2024_Dalarna_kommun.xlsx`
- `rawdata/Servicepunkter_2026_Dalarna.xlsx`
