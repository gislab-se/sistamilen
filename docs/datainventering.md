# Datainventering och proveniens

## Hur uppstartsanteckningarna skapades

`underlag/docs/uppstart_2026-07-03.md` är en kvalitativ
mötesanteckning från möte med Ghada och Alexander den 3 juli 2026. Den
formulerar projektfrågan, två analysidéer (risk- och synergizoner), tänkbara
indikatorer, databehov och en första arbetsgång. Den är ett idé- och
inriktningsunderlag, inte ett reproducerbart analysresultat.

`underlag/docs/forsta_dataprofil.md` skapades däremot av
`underlag/scripts/build_initial_commune_profile.py`. Skriptet läser
de två Excel-filerna, aggregerar rader kommunvis och skriver både en CSV och en
Markdown-sammanfattning. Den första profilen räknade varje aktörs-/tjänsterad
som en ”servicepunkt” och skapade ett viktat screeningtal. Den ska därför ses
som en tidig prototyp.

Två uppgifter i den ursprungliga uppstartsanteckningen har rättats i den nya
datamodellen:

- `sp2026` har 487 innehållsrader, inte 488.
- `Kluster` har 236 innehållsrader, inte 7 772. Det större talet kommer från
  arbetsbokens använda/formaterade radområde och beskriver inte faktiska data.

## Levererade originalfiler

| Fil | Faktiskt innehåll | Analysenhet | Kritisk begränsning |
|---|---|---|---|
| `data/raw/Paketvolymer_2024_Dalarna_kommun.xlsx` | 15 kommuner; Paketbrev, B2C, C2X och B2B; totalt 8 027,494 i källans tusentalsenhet | Kommun, 2024 | Enheten `tst` bör bekräftas med dataägaren; ingen lokal nodvolym |
| `data/raw/Servicepunkter_2026_Dalarna.xlsx`, `sp2026` | 487 unika aktörs-/tjänsterader, 9 aktörer | Aktörserbjudande vid nod, 2026 | En rad är inte nödvändigtvis en egen fysisk plats |
| Samma arbetsbok, `Kluster` | 236 unika adress-/servicenoder | Fysisk källdefinierad nod | Tre mycket närliggande nodpar kräver manuell QA, inte automatisk sammanslagning |
| `underlag/rawdata/Uppdragsbeskrivning paketleveranser_260326.docx.pdf` | Uppdragets bakgrund, frågor, metod och två faser | Styrande uppdragsdokument | Påståendet om Bingsjö/By är inte en verifierad händelsetidslinje |

Excel-filerna i `data/raw` och `underlag/rawdata` är parvis
identiska enligt SHA-256. `data/raw` används som primär sökväg; den äldre
projektmappen är reserv och historik.

## Externa, lokalt sparade underlag

| Fil | Källa | Innehåll |
|---|---|---|
| `data/external/scb/deso_2025_dalarna_raw.geojson` | SCB WFS | Oförändrat råuttag av 175 DeSO 2025 i Dalarnas län |
| `data/external/scb/folkmangd_deso_2024_raw.csv` | SCB Statistikdatabasen TAB6574 | Totalbefolkning och åldersgrupper 65–69, 70–74, 75–79 och 80+ |
| `data/external/scb/source_metadata.json` | Genererat vid hämtning | URL, tid, version, koordinatsystem och kvalitetsutfall |
| `data/external/scb/*_raw.geojson` | SCB WFS | Tätorter 2023, småorter 2023 och fritidshusområden 2020 |
| `data/external/scb/place_areas_source_metadata.json` | Genererat vid hämtning | URL, hash, antal, giltighet och tolkningsnoter per ortslager |

## Härledda analysfiler

| Fil | Rader/objekt | Härledning |
|---|---:|---|
| `data/derived/servicenoder_2026.csv` | 236 | En rad per `kluster_id`, med aktörer, servicetyper, frekvens och raka nodavstånd |
| `data/derived/kommun_screening_fas1.csv` | 15 | Kommunala basmått och fyra separata screeningdimensioner |
| `data/derived/deso_2025_dalarna.geojson` | 175 | DeSO i WGS84 med befolkning, 65+, areal, täthet och nodantal |
| `data/derived/deso_befolkning_2024.csv` | 175 | En rad per DeSO |
| `data/derived/nod_deso_2025.csv` | 236 | Exakt polygonkoppling mellan varje nod och ett DeSO |
| `data/derived/scb_platsomraden_dalarna.geojson` | 369 | 114 tätorter, 181 småorter och 74 fritidshusområden i WGS84 |

## Arbetsregister som ska kompletteras

- `data/working/forandringsregister.csv`: två kandidatposter, Bingsjö och By;
  ingen förändring är ännu primärverifierad.
- `data/working/aktorsmatris.csv`: observerade paketaktörer och uttryckliga
  kandidataktörer; kandidatstatus innebär inte fastställt mandat.
- `data/working/platsfall.csv`: platsidentitet, nodkoppling och frågor.
- `data/working/rus_koppling.csv`: tio spårbara kopplingar till Dalastrategin.
- `data/working/fas1_status.csv`: nuläge per fråga i uppdragsbeskrivningen.

## Reproducerbarhet

- `scripts/build_phase1_outputs.py` bygger nod- och kommunfiler. Befintliga
  arbetsregister skrivs inte över.
- `scripts/fetch_scb_deso.py` hämtar råuttag och bygger DeSO-underlagen.
- `scripts/fetch_scb_place_areas.py` hämtar och normaliserar SCB:s platsområden.
- `tests/` låser radantal, nodidentitet, geografi, Bingsjö-tolkning och SCB-join.
