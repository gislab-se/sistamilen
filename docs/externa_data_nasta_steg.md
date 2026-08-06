# Externa data – genomfört och nästa steg

Kontrollerat 2026-08-05.

## Integrerat utan autentisering

### SCB DeSO och befolkning

- DeSO 2025, 175 områden i Dalarnas län, EPSG:3006 i källan.
- Folkmängd 2024 per DeSO från Statistikdatabasen TAB6574.
- Totalbefolkning, summerad 65+, areal, täthet och antal observerade
  servicenoder.
- Samtliga 236 noder har exakt en DeSO-träff.

Kör: `python scripts/fetch_scb_deso.py`.

### SCB:s historiska platsstruktur

- 114 statistiska tätorter 2023.
- 181 statistiska småorter 2023.
- 74 statistiska fritidshusområden 2020.

Småorts- och fritidshusfälten är områdeskoder, inte ortnamn respektive antal
fritidshus. Lagren används därför enbart som polygonal platsstruktur.

Kör: `python scripts/fetch_scb_place_areas.py`.

## Kräver beställning eller autentisering

### NVDB för bilrestid

Ett restidsnät behöver minst:

- Vägtrafiknät,
- Hastighetsgräns,
- Förbjuden färdriktning,
- gärna Funktionell vägklass som fallback.

Det finns inget enkelt officiellt API-anrop som direkt returnerar en färdig
restidsmatris. Rekommenderat nästa steg är att skapa konto och beställa ett
daterat Dalarna-uttag som GeoPackage i Trafikverkets Lastkajen. Därefter byggs
ett lokalt routbart nät och restid beräknas till första nod, andra nod och nod
med alternativ aktör.

- Registrering: <https://data.trafikverket.se/oauth2/Account/register>
- Lastkajen: <https://lastkajen.trafikverket.se/login>
- API-manual: <https://lastkajen2-p.ea.trafikverket.se/assets/Lastkajen2_API_Information.pdf>

### Dalatrafik via Trafiklab

Statiskt GTFS-uttag:

```text
https://opendata.samtrafiken.se/gtfs/dt/dt.zip?key={apikey}
```

Kräver en Trafiklab-nyckel. Första integrationen bör omfatta hållplatsläge,
avstånd till närmaste hållplats, antal avgångar en vald normal vardag, första
och sista avgång samt antal linjer. Ett lokalt snapshot ska sparas; dashboarden
ska inte fråga API:t vid varje omkörning.

- Dokumentation: <https://www.trafiklab.se/sv/api/gtfs-datasets/gtfs-regional/>
- Nyckel: <https://developer.trafiklab.se/>

## Restidsmåttets acceptanskriterier

Restidsanalysen är leveransklar först när:

1. nätets källa, licens, uttagsdatum och geografiska omfattning är dokumenterade,
2. riktning och hastighet ingår i routingen,
3. oroutbara startpunkter och snap-avstånd redovisas,
4. restid finns till närmaste nod, näst närmaste nod och alternativ aktör,
5. gränsöverskridande alternativ tillåts,
6. ett stickprov har jämförts med manuellt kontrollerade rutter,
7. raka avstånd inte längre visas eller etiketteras som vägrestid.

Till dess är dashboardens nodavstånd uttryckligen fågelvägsavstånd och används
endast för screening.
