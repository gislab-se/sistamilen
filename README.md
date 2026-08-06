# Paketleveranser i Dalarna – Fas 1

En lokal Streamlit-dashboard och ett reproducerbart analysunderlag för den
inledande kartläggningen i Region Dalarnas uppdrag om paketleveranser.

Dashboarden skiljer genomgående mellan:

- 236 källdefinierade fysiska adress-/servicenoder,
- 487 observerade aktörs-/tjänsterader vid dessa noder,
- dokumenterade uppgifter som behöver verifieras,
- reproducerbara screeningmått som inte är ett fastställt riskindex.

## Dashboardens sidor

- **Lägesbild:** regional karta, nyckeltal och sammanfattad Fas 1-status.
- **Servicenät:** filter, noder, aktörer, servicetyper, observerad redundans och QA-register.
- **Tillgänglighet och bortfall:** nuläge och hypotetiska nodbortfall med befolkning på 1 km-rutor och DeSO-summering.
- **Screening:** befolkningsviktade avstånd från 1 km-rutor till första nod,
  andra nod och alternativ aktör samt ett separat redundansgap, utan sammanslaget index.
- **Platsfall:** Bingsjö och By, med fakta och verifieringsbehov åtskilda.

Under **Underlag** finns **Geografiska lager** med DeSO och historiska
platslager samt **Metod och status** med uppdragsfrågor, RUS-spårbarhet och
databeredskap. Den beslutade målbilden och etappindelningen finns i
`docs/dashboard_malbild.md`.

## Starta på port 8503

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync
uv run streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8503
```

Öppna <http://127.0.0.1:8503>. Kontrollera servern med:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8503/_stcore/health
```

## Bygg analysfiler

De lokala Excel-filerna bearbetas utan nätåtkomst:

```powershell
uv run python scripts/build_phase1_outputs.py
```

SCB:s officiella DeSO-geometri och befolkning hämtas till daterade råkopior och
bearbetade filer:

```powershell
uv run python scripts/fetch_scb_deso.py
uv run python scripts/fetch_scb_place_areas.py
uv run python scripts/fetch_scb_population_grid.py
```

Streamlit hämtar aldrig extern data vid sidladdning; appen läser de lokalt
sparade uttagen.

## Källor och tidsreferenser

| Källa | Tid | Geografisk nivå | Användning |
|---|---:|---|---|
| `Paketvolymer_2024_Dalarna_kommun.xlsx` | 2024 | Kommun | Paketbrev, B2C, C2X och B2B; källrubrik `tst` |
| `Servicepunkter_2026_Dalarna.xlsx` | 2026 | Nod och aktörserbjudande | Noder, aktörer, tjänstetyper och leveransfrekvens |
| SCB DeSO 2025 | version 2025 | DeSO | Polygoner och kommunanknytning |
| SCB TAB6574 | 2024-12-31 | DeSO | Befolkning totalt och summerad 65+ |
| SCB befolkning 1 km-rutor | 2025 | 1 × 1 km-ruta | Hypotetisk bortfallssimulering, totalbefolkning och 65+ |
| Dalastrategin 2030, upplaga 2026 | 2026 | Regional strategi | Spårbar RUS-koppling |

Paketvolymerna och serviceutbudet avser olika år. Kommunvolymer får inte
beskrivas som lokal efterfrågan vid en nod. DeSO är statistiska områden, inte
automatiskt funktionella upptagningsområden.

## Viktiga filer

- `dashboard_data.py` – datakontrakt och härledningar.
- `dashboard_ui.py` – cachad laddning och kartfunktioner.
- `scripts/build_phase1_outputs.py` – fysiska noder och arbetsregister.
- `scripts/fetch_scb_deso.py` – reproducerbar SCB-hämtning.
- `scripts/fetch_scb_place_areas.py` – tätort/småort 2023 och fritidshusområde 2020.
- `scripts/fetch_scb_population_grid.py` – befolkning på 1 km-rutor 2025 för Dalarna.
- `data/working/forandringsregister.csv` – verifieringsbart händelseregister.
- `data/working/aktorsmatris.csv` – observerade och möjliga aktörer/roller.
- `data/working/rus_koppling.csv` – spårbar RUS-matris.
- `docs/fas1_leveransspecifikation.md` – evidensnivåer och acceptanskriterier.
- `docs/dashboard_malbild.md` – informationsarkitektur, gemensamma begrepp och genomförandeetapper.
- `docs/datainventering.md` – originaldata, proveniens och korrigerade radantal.
- `docs/externa_data_nasta_steg.md` – NVDB- och GTFS-beredskap.

## Testa

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q streamlit_app.py dashboard_data.py dashboard_ui.py app_pages scripts tests
```

## Kvarvarande externa beroenden

- Vägnätsbaserad bilrestid kräver ett NVDB-uttag för Dalarna eller konto till
  Trafikverkets Datautbytesportal/Lastkajen.
- Dalatrafiks statiska GTFS kräver en Trafiklab-nyckel.
- Bingsjös och Bys serviceförändringar måste primärverifieras med kommun,
  lokal nod och berörda paketaktörer.

Till dess visas raka avstånd tydligt som screeningmått, aldrig som vägrestid.
