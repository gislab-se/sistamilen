# Transportnärvaro från DVA:s sophämtning

Fristående interaktiv screeningkarta för att undersöka möjlig samordning mellan
paketservice och Dala Vatten och Avfalls sophämtning under 2026. Prototypen är
inte kopplad till Streamlit-appen.

## Öppna kartan

Öppna `index.html` i en webbläsare. Leaflet, traktdata och paketnodsdata finns
lokalt i prototypmappen. Internetanslutning behövs endast för OpenStreetMaps
bakgrundskarta.

Kartan visar:

- 35 publicerade DVA-trakter i Gagnef, Leksand, Rättvik och Vansbro,
- 1 830 publicerade hämtningshändelser för 2026,
- 47 observerade paketservicenoder i de fyra kommunerna,
- filter för kommun, veckodag, avfallsslag och hämtningsdatum,
- paketnoder med endast en observerad aktör,
- källflaggor för stavfel och datum som avviker från traktens veckodag.

## Viktig avgränsning

Traktmarkörerna är geokodade ankarorter. De är inte faktiska körvägar,
traktgränser, hämtställen eller beräknade fordonspositioner. Den streckade
7-kilometersringen är endast en illustrativ närzon för att upptäcka möjliga
överlapp med paketnoder. Den får inte användas som ett avstånds- eller
täckningsmått.

Webbschemat gäller huvudsakligen fastigheter med egna kärl. Gemensamma
hämtställen och fritidshus kan ha andra scheman och behöver kompletteras med
data från DVA.

## Bygg om

Från projektroten:

```powershell
.\.venv\Scripts\python.exe scripts\build_dva_standalone_map.py
```

Utan flaggor används den lokalt sparade källsidan och geokodningscachen. För
att hämta den aktuella publika sidan:

```powershell
.\.venv\Scripts\python.exe scripts\build_dva_standalone_map.py --refresh-source
```

Använd `--refresh-geocodes` endast när traktankarna verkligen ska geokodas om.
Geokodningen använder OpenStreetMap Nominatim och gör högst ett sekventiellt
uppslag per sekund.

## Filer

- `index.html` – färdig fristående karta.
- `data/dva_trakter_2026.csv` – trakter och geokodade ankare.
- `data/dva_schema_2026.csv` – normaliserade hämtningsdatum.
- `source/sophamtningsschema_2026.html` – lokalt källsnapshot.
- `source/tract_anchor_geocodes.json` – geokodningscache och proveniens.
- `vendor/` – lokal Leaflet 1.9.4-distribution och licens.

Källa: <https://www.dalavattenavfall.se/avfall-och-atervinning/sophamtningsschema.html>
