# Transportnärvaro från DVA:s sophämtning

Fristående interaktiv screeningkarta för att undersöka möjlig samordning mellan
paketservice och Dala Vatten och Avfalls sophämtning under 2026. Prototypen är
även tillgänglig som **Sophämtningskarta** i huvudappen `streamlit_app.py`.

## Öppna kartan

Öppna `index.html` i en webbläsare eller **Sophämtningskarta** i huvudappen:
<http://127.0.0.1:8503/waste_routes>. Detta är en egen karta med lokala
kartresurser och ett offentligt DVA-/servicedataset, utan transportloggar.
Huvudappen bäddar in alla kartresurser och behöver ingen extra kartserver.
Internet behövs endast för valbar OpenStreetMap-bakgrund. Lokal SCB-bakgrund finns.
Den separata fliken **Sophämtning + transporter + service** finns på
<http://127.0.0.1:8503/samordning>. Där kan trakter, fordonsrutter och servicepunkter
jämföras på samma karta med gemensamt datum- och kommunfilter.

Kartan visar:

- 35 publicerade DVA-trakter i Gagnef, Leksand, Rättvik och Vansbro,
- 1 830 publicerade hämtningshändelser för 2026,
- 293 unika namngivna platsbeskrivningar inom trakter: 185 ort-/platsträffar,
  53 osäkra/tolkade ort-/gatuträffar och 55 tydligt märkta reserver vid traktankare,
- 47 observerade paketservicenoder i de fyra kommunerna,
- tänd/släck per kommun och trakt,
- kommun- och datumfilter, traktens veckodag och avfallsslag,
- CSV-export av valda platser med källtext, precision, matchningsstatus och källa,
- paketnoder med endast en observerad aktör,
- källflaggor för stavfel och datum som avviker från traktens veckodag.

## Viktig avgränsning

Sophämtningsmarkörerna anger orter och gator ur publicerade traktbeskrivningar.
De är inte faktiska körvägar, traktgränser, hämtställen eller fordonspositioner.
Källans sammansatta texter delas endast med dokumenterade regler, till exempel
`Högberget Skampervägen` och `Hedslund/Nyheden`; originaltexten bevaras.
SCB:s tätort/småort 2023 samt offentliga OSM-namn inom rätt kommun används.
Gatupunkter och tolkade delområden behöver granskas. Platser utan entydig träff
visas grått vid traktens befintliga ankarpunkt. De bevisar inte platsens läge.
De tidigare illustrativa 7-kilometersringarna kan fortfarande visas per traktankare.
De anger inte traktgräns eller täckning och påverkar inga jämförelsemått.

## Den separata gemensamma fliken

**Sophämtning + transporter + service** visar dessutom 20 namngivna fordonslager
och beräknade NVDB-rutter. Alla tre underlagen är tända från start och kan
begränsas med lagerreglage. I hela reseloggens vecka finns sex ort-/datumträffar.

Ort-/datumjämförelsen använder samma SCB-tätort/småort 2023 för punkter inom
dess polygon; stadsdelar som Noret kan därmed jämföras med postorten Leksand.
Utanför dessa områden krävs matchat ortnamn inom samma kommun. Kartpunktens
precision påverkar jämförelsen och redovisas i tabellen. Sophämtningens
reservpunkter och fordonsrutternas vägpassager räknas inte som överlapp.
Flera avfallsslag samma dag räknas inte som flera bilar eller separata besök.
En detaljresa räknas en gång per ort/datum även om båda ändpunkterna ligger där.
Ingen samtidighet, ledig kapacitet, gemensam besöksadress eller paketleverans antas.

Hämtningsdatum kan väljas för hela 2026. Reseloggen omfattar endast
21–27 september; utanför den veckan visas inga registrerade detaljresor eller
ort-/datumträffar. Fredriksberg ligger i Ludvika och ingår inte i DVA:s fyra kommuner.

Webbschemat gäller huvudsakligen fastigheter med egna kärl. Gemensamma
hämtställen och fritidshus kan ha andra scheman och behöver kompletteras med
data från DVA.

## Bygg om

Från projektroten:

```powershell
uv sync --group routing --cache-dir .uv-cache
.\.venv\Scripts\python.exe scripts\build_dva_standalone_map.py
```

Utan flaggor används den lokalt sparade källsidan och geokodningscacherna; inga
nya uppslag för de 293 platsbeskrivningarna görs. För
att hämta den aktuella publika sidan:

```powershell
.\.venv\Scripts\python.exe scripts\build_dva_standalone_map.py --refresh-source
```

Använd `--refresh-geocodes` endast när traktankarna verkligen ska geokodas om.
Geokodningen använder OpenStreetMap Nominatim och gör högst ett sekventiellt
uppslag per sekund.

De utökade platsmatchningarna byggs också av:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_dva_place_points
```

Flaggan `--download-public-places` hämtar ett fast offentligt länsuttag med
OSM-orter och gator, utan reseloggar eller besöksadresser i frågan.
`--lookup-public-names` gör cachade engångsuppslag av kvarvarande offentliga
namn från DVA:s schema, minst 1,2 sekunder mellan anrop, och stoppar vid HTTP-fel.
Ingen geokodning görs när kartan öppnas. Uttag och metadata finns i
`data/external/osm/dva_named_places.json.gz` och tillhörande metadata.

## Filer

- `index.html` – färdig fristående karta.
- `index.template.html`, `app.js`, `styles.css` – den egna sophämtningskartans gränssnitt.
- `data/dva-places.json` och `.js` – offentliga DVA-platser, schema och servicenoder;
  inga transportloggar eller kopplingar till transportadresser ingår.
- `data/geography.js` – lokal offentlig SCB-bakgrund.
- `model.js` – genererad kopia av den gemensamma filtrerings-/platsmodellen.
- `data/dva_trakter_2026.csv` – trakter och geokodade ankare.
- `data/dva_schema_2026.csv` – normaliserade hämtningsdatum.
- `data/dva_platser_2026.csv` – utökade platsmatchningar och granskningsbehov.
- `source/sophamtningsschema_2026.html` – lokalt källsnapshot.
- `source/tract_anchor_geocodes.json` – geokodningscache och proveniens.
- `source/tract_place_queries.json` – sparade uppslag av offentliga platsnamn.
- `../fredriksberg_resor/data/waste-data.json` och `.js` – gemensamt kartdataset,
  kommun- och SCB-ortkoppling för transportadresserna samt proveniens.
- `../fredriksberg_resor/waste-model.js` – filter och dubbleringsfri ort-/datumjämförelse.
- `vendor/` – lokal Leaflet 1.9.4-distribution och licens.

Källa: <https://www.dalavattenavfall.se/avfall-och-atervinning/sophamtningsschema.html>
