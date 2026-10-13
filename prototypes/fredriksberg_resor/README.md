# Transporter i Dalarna – lokal granskningskarta

Fristående HTML/JavaScript-app för det nya reseunderlaget i
`data/fredriksberg/fwdpaketleveranser.zip`. Visar hela underlaget med snabbfilter
för Fredriksberg. Appen är förberedd för granskning i det befintliga
GitHub-projektet `gislab-se/sistamilen`; ingen uppladdning eller publicering har gjorts.
Samma karta finns nu som **Transportanalys** i huvudappen på lokal port 8503,
med länkar till sophämtningskartan och tillgänglighets-/bortfallsanalysen.
Huvudappen bäddar in kartans lokala filer och kräver inte servern på port 8765.
Transportanalys och Sophämtningskarta är separata vyer. Den nya fliken
**Sophämtning + transporter + service** på <http://127.0.0.1:8503/samordning>
använder den gemensamma kartan med DVA:s 35 traktlager, 293 namngivna platser/gator,
paketnoder och fordonsrutter. För lokal HTML-visning kan `index.html?compare=1`
öppna samma gemensamma vy. Den egna sophämtningskartan ligger i DVA-prototypen.
Gemensamt datum- och kommunfilter styr båda; avfalls- och traktfilter styr DVA.
Ort-/datumträffar använder SCB:s tätort/småort eller matchat ortnamn inom kommunen,
utan att tolka rutternas vägpassager som besök. Se DVA-prototypens README för metod.

## Öppna

Öppna `index.html` direkt i Edge, Chrome eller Firefox. Kartbibliotek, data och
geografisk bakgrund finns lokalt. OpenStreetMaps bakgrundskarta är påslagen
från start och behöver internet; den kan stängas av. Då visas lokal SCB-geometri.
Appen skickar inga adressuppslag vid sidladdning eller filtrering.

För en lokal server, från projektroten:

```powershell
.\.venv\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1 --directory prototypes\fredriksberg_resor
```

Öppna <http://127.0.0.1:8765>.

## Innehåll

- 1 116 detaljerade resor den 21–27 september 2026, 20 fordon och 272 adresser.
- Datum-, fordons-, ort- och fritextfilter; 14 resor med start eller stopp i Fredriksberg.
- 20 fordonslager med tänd/släck-reglage, färger, antal resor per lager och snabbval
  för att tända eller släcka alla. Lagren styr karta, reselista, nyckeltal, kvalitet,
  månadssummering och CSV-export. Datum-/orts-/sökfilter begränsar lagrens resor.
- Namn baserat på de tre vanligaste besöksorterna under detaljveckan, till exempel
  **Fredriksberg / Falun / Mora · T07**. Orternas ordning är inte en fast rutt;
  namnen anger inte verksamhet eller operatör. Registreringsnummer ersätts med
  transport-ID i exporterad JSON/JavaScript, resor och summeringar.
- Växling mellan adresspunkter och ortankare, beräknade NVDB-vägrutter, schematiska resrelationer och valbara paketservicenoder 2026.
- Zoomning med +/−, scroll, tangentbord och nypgest; bakgrundskarta från OpenStreetMap.
- Alla 272 adresser kan visas geografiskt: 82 adressmatchningar,
  164 ungefärliga gatu-/husträffar, 12 plats-/verksamhetsträffar och
  14 reservpunkter vid ortcentroid/ortankare.
- Grönt visar matchningar, orange osäkra träffar och grått ortreserv.
  Osäkra träffar och ortreserver listas under Datakvalitet.
- Reselista med källblad och radnummer i resans kartdialog; CSV-export av valda resor.
- Datakvalitet: 1 218 rapporterade resor i dagssummeringarna, 1 116 detaljrader,
  en skillnad på 102 resor fördelad på 102 fordons-/dagsrader.
- Separat månadssummering: 5 403 rapporterade resor och 73 400 km i september.

## Vad kartan säger

### Beräknade vägrutter med funktionell vägklass

Välj **Beräknade vägrutter · NVDB** eller **Schematiska resrelationer** i sidpanelen.
Snabbvalet **Pilot: Fredriksberg · 23 september** visar en dag med tidsordnade resor,
numrerade ankomster och färdriktningspilar. Klicka på en resa för att jämföra
registrerad körsträcka/restid med modellens värden. Flera besök kan dela kartpunkt.
Paketservicenoder visas som referenslager; de är inte automatiskt besök i reseloggen.
Linjer kan färgas efter fordonslager eller funktionell vägklass. Beräkningsvikterna
för vägklass ändras inte när färgsättningen växlas. En gemensam sträcka kan användas
av flera fordon och överlappa; tänd/släck lagren för att jämföra dem. Lagerreglage
behåller kartans utsnitt. Välj ett fordon och ett datum för den detaljerade dagsvyn.
Riktningspilar kan stängas av i sidpanelen. Pilar visas bara i synligt kartutsnitt,
med mindre storlek och glesare placering i översikten. Överlappande rutter delar
utrymmet mellan pilarna. Vid zoomning och förflyttning uppdateras placeringen.
Färdriktningarna ritas parallellt på varsin sida av vägen, med ett visuellt
avstånd som anpassas efter zoom. Förskjutningen visar riktning och representerar
inte körfält eller verkliga vägbanors läge. Ruttberäkning och sträcka ändras inte.

Vägnätet läses från det angivna lokala `Dalarnas_län.gpkg`, med betraktelsedatum
2026-08-18, SWEREF 99 TM och CC0 enligt leveransinformationen. Originalet ändras
inte eller kopieras till appen. Endast beräknade ruttgeometrier och metadata sparas.
NVDB:s topologiska nod-ID används, så korsande vägar utan anslutning kopplas inte ihop.
Attribut kopplas via länksekvens och linjära lägesmått. Bilnät, förbjuden färdriktning,
allmänna motortrafikförbud och svängförbud för allmän trafik ingår.

[Funktionell vägklass](https://bransch.trafikverket.se/TrvSeFiler/Dataproduktspecifikationer/V%C3%A4gdataprodukter/DPS_E-G/1010funktionell_vagklass.pdf)
beskriver vägens betydelse i nätet: 0 är högst och 9 lägst. Den anger inte i sig
bredd, skick eller tillåtlighet för ett visst tungt fordon. För denna granskningsmodell
minimeras restid multiplicerad med en preferensfaktor för vägklass 0–9:
`1; 1,02; 1,08; 1,15; 1,25; 1,4; 1,6; 1,9; 2,3; 2,8`.
Faktorerna är ett valt scenario, inte officiella NVDB-värden. Lägre klasser
prioriteras, samtidigt som lokala anslutningsvägar tillåts. Pilar och färger
visar beräknad riktning och vägklassgrupp. Ruttgeometrin förenklas med 3 meter.
Omedelbar vändning tillbaka på samma segment får 90 sekunders extra sökkostnad
om det finns andra anslutningar; kostnaden ingår inte i redovisad modellrestid.

Modellrestid beräknas med 80 procent av registrerad hastighetsgräns, utan köer,
stopptider eller korsningsfördröjningar. Om hastighet saknas används klassbaserade
antaganden 110/100/90/80/70/60/50/40/30/20 km/h; berörd sträcka sparas i ruttdata.
Detta är en profil för lätt motorfordon. Fordonens vikt, höjd och bärighetsbehov är
inte kända. Allmänna trafik- och svängförbud tillämpas konservativt även vid
tidsvillkor/undantag. Tungfordonskrav, undantagsrätt och andra villkor måste granskas
innan operativ användning. Se även [Trafikverkets beskrivning av ruttning med NVDB](https://lastkajen.trafikverket.se/assets/Ruttning_med_NVDB.pdf).

Adress-/reservpunkter ansluts till närmaste tillgängliga bilvägssegment inom
1 500 meter. Anslutningsavstånd och adressprecision visas i resans dialog.
Det avståndet räknas inte som körväg och ritas inte som en påhittad anslutningsväg.
Även i ortvyn beräknas rutterna från adress-/reservpunkterna. Osäkra gatu- och
ortpunkter gör därför även rutterna osäkra. Filipstadsvägen 36 är fortfarande
en gatuträff; exakt besöksentré behöver verifieras.

Resultat för hela underlaget: **928** resor med beräknad vägrutt, **141** med samma
anslutna kartpunkt, **14** utan närliggande väg i länsuttaget och **33** utan
sammanhängande tillåten förbindelse i profilen. De senare får ingen påhittad linje.
En registrerad resa med samma punkt kan innehålla en slinga; modellvärdet lämnas
utan rutt i stället för att hävda att fordonet körde noll kilometer.

Pilotsträckan Fredriksberg–Mora den 23 september blir 129,849 km jämfört med
131 km i Excel. Cirka 99 procent ligger i vägklass 0–3. Det är en rimlighetskontroll,
inte bevis för faktiskt körväg. Reskedjans ordning följer detaljbladens starttider;
adressluckor och saknade detaljrader flaggas. Ingen extra förflyttning eller återresa skapas.

**Fredriksberg är inte start i alla rutter.** Alla 14 detaljresor som berör orten
tillhör **Fredriksberg / Falun / Mora · T07**. Den 23 september börjar dess första registrerade resa där, men
den 22 september börjar första detaljresan på Vasagatan 12 i Falun. Första
registrerade start ska inte tolkas som fordonets säkra depå när detaljunderlag saknas.

Bygg om ruttdata lokalt efter ändringar av adresser eller reseunderlag:

```powershell
uv sync --group routing --cache-dir .uv-cache
.\.venv\Scripts\python.exe scripts\build_nvdb_review_routes.py --gpkg "C:\gislab\data\data_raw\lastkajen\dalarna\Dalarnas_län.gpkg"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_nvdb_review_routes.py -v
```

Ruttdata i `data/road-routes.json` och `.js` innehåller proveniens, källdatum,
klassvikter, profil, anslutningsavstånd, klassfördelning och koppling till varje
detaljresas ID. Byggsteget gör inga nätanrop. Vanlig visning kräver ingen ruttserver.

Excel innehåller start-/stoppadresser, tider, körsträcka, restid och stopptid,
men inga GPS-koordinater, körvägsgeometrier eller paketvolymer. En resa är därför
en fordonsobservation och får inte automatiskt tolkas som en paketleverans.

I ortvyn har alla 272 adresser ungefärliga ortankare. Flera adresser på samma ort delar
samma kartpunkt. SCB:s tätorter 2023 används med centroid för största
delpolygonen. Fredriksbergs östra och västra tätorter sammanvägs efter polygonarea.
`Floda / Dala-Floda` kopplas uttryckligen till postorten Dala-Floda. För Gustafs
och Krylbo, som saknar en motsvarande namngiven polygon i det lokala uttaget,
används medelpunkten för postortens befintliga paketservicenoder.

Sex ytterligare offentliga tätortsgeometrier (Fagersta, Kungsgården, Sala,
Storvik, Storvreta och Uppsala) hämtades från
[SCB:s officiella öppna geodata](https://www.scb.se/vara-tjanster/oppna-data/oppna-geodata/).
Detta referensuttag skickar enbart ortnamn till SCB. Originalgeometri, exakt
fråge-URL, hämtningsdatum och SHA-256 sparas i `source/`.

Adressvyn använder lokal matchning mot befintliga servicenodskoordinater och
ett offentligt OSM-adressuttag för hela Dalarna, Uppsala, Västmanland och Gävleborg.
Den fasta uttagsfrågan innehåller enbart länskoder, aldrig besöksadresser,
fordonsuppgifter eller tider. Matchningen görs på datorn efter nedladdning.
För en adressmatchning måste gatunamn och hela husnumret matcha. Ortankare
och postnummer används för geografisk kontroll. Träffar med avvikande postnummer
visas i orange. Geografiskt åtskilda, tvetydiga adresskandidater lämnas utan punkt.

Efter uttryckligt godkännande skickades de återstående 192 adresstexterna till
OpenStreetMap Nominatim. Personnamn, fordon och besökstider skickades inte.
Svar och frågetidpunkter sparas i `source/nominatim_queries.json`. Om hela
husnumret saknas men gatan kan placeras används en representativ gatupunkt,
tydligt markerad som ungefärlig i orange. Flera adresser med samma gatupunkt
grupperas, med ursprungsadresserna kvar i popupen. Grön markering kräver träff
på gatunamn och hela husnumret utan identifierad postnummeravvikelse.

OSM-punkter kan representera en adressnod eller mitten av en byggnads omslutande
rektangel; de är inte uppmätta fordonspositioner eller alltid entrépunkter.
Den utökade sökningen rensar bland annat överflödig orttext och provar
verksamhetsnamn, exempelvis `vårdcentral, Sunnansjö, Sverige`, och gatunamn
utan husnummer. Namngivna platsträffar kontrolleras mot namn, typ och ort.
En verksamhetsträff på ett närliggande objekt behöver fortfarande granskas
och får orange markering.

För Vårdcentralen Sunnansjö hittades en officiell kartkoordinat i
[1177:s kontaktkort](https://www.1177.se/hitta-vard/kontaktkort/Vardcentral-Sunnansjo/),
som anger Sjukstugevägen 3. Den används för både verksamhetsnamnet och den
matchande gatuadressen. Källa, besöksadress, koordinat, hämtningsdatum och
sidans SHA-256 sparas i `source/public_place_coordinates.json`.

Adresser utan träff läggs i stället vid ortens centroid som grå reservpunkter.
Flera adresser på samma ort delar då en punkt, med varje originaladress kvar
i popupen. För postorten Gustafs används den omslutande SCB-tätortens centroid
(Enbacka, Mora och Naglarby). Krylbo använder ett dokumenterat ortankare från
paketnodernas medelpunkt eftersom det lokala uttaget saknar en egen Krylbo-polygon.
Reservpunkterna visar inte faktiska besöksadresser och listas under Datakvalitet.

Filipstadsvägen 36 i Fredriksberg visas på gatunivå:
gatan hittades, men husnummer 36 behöver fortfarande verifieras. Dess 14 resor
kan granskas i både adress-/gatuvyn och ortvyn.

Alla resor och nyckeltal finns kvar. Texten under kartan anger antalet
reservpunkter. Alla adresser kan nu visas, men gatupunkter och ortreserver
ger en ungefärlig geografisk bild; de bevisar inte fordonets exakta position.

Offentligt OSM-originaluttag, datum, exakt fråga och SHA-256 finns i
`data/external/osm/review_county_addresses.json.gz` och tillhörande metadata.
Matchningar och proveniens finns i `source/address_matches.json`;
`data/adressmatchning.csv` kan laddas ned från kvalitetsvyn.

För en uttryckligen godkänd engångskörning av återstående Nominatim-uppslag:

```powershell
.\.venv\Scripts\python.exe -m scripts.geocode_review_nominatim --authorized-lookups
.\.venv\Scripts\python.exe scripts\build_fredriksberg_review.py
```

Lägg till `--expand-places` för de bredare plats-/verksamhetssökningarna.
En vanlig ombyggnad läser de sparade resultaten och lägger automatiskt till
ortcentroid/ortankare för kvarvarande adresser. Den officiella Sunnansjö-källan
kan vid behov uppdateras med `python -m scripts.import_review_public_places`.

Följ [Nominatims användningsvillkor](https://operations.osmfoundation.org/policies/nominatim/):
en tråd, en dator, högst ett anrop per sekund och permanent cache. Skriptet
begränsar sig till detta granskningsunderlag, gör minst 1,2 sekunders mellanrum
och stoppar vid HTTP-avvisning. Appen använder bara sparade resultat.
En vanlig ombyggnad kräver inga nya adressuppslag.

I läget **Schematiska resrelationer** visar linjerna sammanslagna samband mellan valda kartpunkter i båda
riktningarna. De visar inte körvägar, GPS-spår eller möjliga samordningssträckor.
Körsträckor och restider hämtas från Excel. De beräknas inte från linjerna.
DeSO 2025 ger en lokal geografisk bakgrund. Kartskalan är kartans skala och
ska inte användas för att mäta resornas körsträcka.

Tider återges utan omräkning enligt Excel, med arbetsreferensen Europe/Stockholm;
källan saknar uttrycklig tidszon. CO₂ saknar angiven enhet och visas endast som källvärde.

Dag- och månadssummeringar adderas inte till detaljresorna. Datum- och
fordonsfilter gäller kvalitetstabellen; ort- och fritextfilter kan inte
tillämpas på summeringar utan adresser. Månadstabellen följer endast fordonsfiltret.

## Bygg om utan nätåtkomst

```powershell
.\.venv\Scripts\python.exe scripts\build_fredriksberg_review.py
```

Originalzipen ändras inte. Skriptet läser den direkt, bevarar källrad/blad,
avdubblar överlappande detaljresor och sparar normaliserade JSON- och CSV-filer.
Arkivets och varje Excel-fils SHA-256 sparas i datans metadata. Det saknade
detaljunderlaget fylls inte med antagna resor.

För att uppdatera enbart det offentliga SCB-referensuttaget för de sex extra orterna:

```powershell
.\.venv\Scripts\python.exe scripts\build_fredriksberg_review.py --refresh-places
```

För att räkna om adressmatchningen från det sparade offentliga kartuttaget:

```powershell
.\.venv\Scripts\python.exe -m scripts.geocode_review_addresses
.\.venv\Scripts\python.exe scripts\build_fredriksberg_review.py
```

En uttrycklig `--download-public-map`-flagga till första kommandot hämtar på
nytt det fasta länsuttaget. Den lokala appen anropar aldrig Overpass API.
Se [Overpass användningsinformation](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html).
OSM-data används med attribution enligt ODbL 1.0.

Granskade adresskoordinater kan komplettera adressvyn genom en CSV med
kolumnerna `address,lon,lat,source`, i WGS84:

```powershell
.\.venv\Scripts\python.exe scripts\build_fredriksberg_review.py --coordinates data\fredriksberg\adresskoordinater.csv
```

`address` ska motsvara hela Excel-adressen. Ange källa för varje koordinat.
Webbkartan gör ingen automatisk adressgeokodning vid användning.

## Kontrollera

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_fredriksberg_review.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_review_address_matching.py -v
node tests\test_fredriksberg_model.cjs
node --check prototypes\fredriksberg_resor\app.js
```

## Inför senare GitHub-granskning och publicering

Appmappen kan serveras statiskt utan byggsteg. Registreringsnummer finns inte i
appens exporterade data. En lokal kopplingsnyckel till originalets fordons-/bladnamn
sparas i `.runtime/fredriksberg-review/vehicle-key.json`, utanför appmappen och
ignorerad av Git. Originalzip/Excel ändras inte. Detta är pseudonymisering:
adresser, tider och originalfilnamn kan fortfarande innehålla identifierande uppgifter.
Kontrollera hela `prototypes/fredriksberg_resor/` före en uppladdning. Bestäm vilka
uppgifter som ska ingå i en delad eller publicerad version. Originalzip och
Excel-filer behöver inte ingå i publiceringsmappen.

Leaflet 1.9.4 och dess licens finns i `vendor/`, återanvända från den befintliga
DVA-prototypen. SCB-källorna är de lokalt sparade uttagen i `data/derived/`
och kompletteringen i `source/`. Valbar bakgrundskarta:
[OpenStreetMap](https://www.openstreetmap.org/copyright).
