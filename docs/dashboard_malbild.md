# Målbild för Fas 1-dashboarden

Senast uppdaterad: 2026-08-06

## Syfte

Dashboarden ska hjälpa projektgruppen att gå från regional orientering till ett
spårbart urval av platser och scenarier. Den ska inte presentera en automatisk
eller sammanslagen riskpoäng. Varje vy ska tydligt skilja mellan observerad
källdata, beräknade mått, hypotetiska scenarier och uppgifter som återstår att
verifiera.

## Rekommenderad informationsarkitektur

Dashboardens fem huvudsakliga arbetsflöden är:

1. **Lägesbild** – regional omfattning, centrala nyckeltal och läget i Fas 1.
2. **Servicenät** – noder, aktörer, servicetyper, leveransfrekvens och observerad redundans.
3. **Tillgänglighet och bortfall** – nuläge på 1 km-rutor samt simulering av en eller flera borttagna noder.
4. **Screening** – separata, transparenta prioriteringsdimensioner för kommuner och senare platser.
5. **Platsfall** – verifieringsbara platskort och jämförelser för prioriterade fall.

**Metod, källor och status** är en sekundär sida för spårbarhet, RUS-koppling,
databeredskap och arbetsbacklog. DeSO och historiska platslager är analyslager i
arbetsflödena, inte ett självständigt slutresultat.

## Gemensamma analysenheter

| Analysenhet | Primär användning | Ska inte tolkas som |
|---|---|---|
| 1 km-ruta | Befolkningsnära tillgänglighet, avstånd och bortfall | Exakt adress eller faktiskt resmönster |
| DeSO | Demografisk kontext, officiell summering och rapportering | Ett homogent upptagningsområde |
| Kommun | Regional jämförelse, urval och prioritering | Lokal variation inom kommunen |
| Fysisk nod | Utbudspunkt, aktörsbredd och scenarioobjekt | En aktörstjänst |
| Aktörstjänst | En aktörs erbjudande vid en fysisk nod | En unik fysisk plats |

## Evidensetiketter

- **Observerat:** direkt uppgift i angiven källa och referensperiod.
- **Beräknat:** reproducerbart resultat från källdata och dokumenterad metod.
- **Scenario:** hypotetisk förändring; källdatan ändras inte.
- **Ej verifierat:** uppgift eller händelse som kräver primärkälla eller lokal bekräftelse.
- **Datagap:** nödvändigt underlag saknas eller är otillräckligt.

## Gemensam sidlogik

Varje analyssida bör följa samma ordning:

1. Fråga, geografiskt urval och referensperiod.
2. Kontroller till vänster, huvudkarta i mitten och sammanfattning till höger när karta är central.
3. Nyckeltal och förklarande text som besvarar vad urvalet betyder.
4. Fördjupande diagram och tabeller.
5. Metod, källor och begränsningar längst ned.

Färger ska ha samma betydelse inom en vy. Benämningarna *berörd*, *exponerad*
och *faktiskt påverkad* får inte användas som synonymer. Kartor ska behålla
stabil position och identitet vid widgetändringar; dyra inställningar samlas i
formulär eller avgränsade körningar.

## Etappindelning

### Etapp 1 – struktur och orientering

- Inför de fem huvudflödena och en sekundär metod-/statussida.
- Slå ihop regional överblick med en kort Fas 1-status.
- Flytta aktörs- och servicetypdiagram till Servicenät.
- Behåll fin geografi som återanvändbart lager och gör den gamla sidan sekundär.
- Rätta inaktuella backlogtexter och förtydliga evidensnivåer.

### Etapp 2 – analytisk skärpa

- **Genomfört 2026-08-06:** Screening använder befolkningsviktade mått från
  1 km-rutor till första nod, andra nod och alternativ aktör samt ett separat
  redundansgap. Måtten visas var för sig och använder tills vidare fågelvägsavstånd.
- Koppla urval i Screening vidare till Platsfall och bortfallsscenario.
- Lägg till scenarioexport och sparade scenariojämförelser.

### Etapp 3 – externa beroenden och validering

- Ersätt fågelvägsavstånd med vägnätsbaserad restid.
- Verifiera Bingsjö, By och andra förändringsfall med datum, beslut och ersättning.
- Komplettera med arbetsställen, fritidshus, kollektivtrafik och lokala intervjuer.
- Validera RUS-kopplingar, ansvar och slutsatser med beställare och berörda aktörer.

## Klart för Fas 1

Fas 1 kan betraktas som leveransklar när förändringsfallen är verifierade,
tillgänglighet till alternativa lösningar är beräknad, riskzoner och trösklar är
dokumenterade, jämförelseplatser är transparent valda, aktörsansvar och
RUS-kopplingar är validerade samt alla slutsatser är reproducerbara och märkta
med rätt evidensnivå.
