# Fas 1 – leveransspecifikation för kartläggning av paketleveranser i Dalarna

## Syfte och avgränsning

Fas 1 ska ge en fördjupad och regionalt jämförbar förståelse för vilka samhällen och geografier som har påverkats eller är sårbara. Leveransen ska skilja mellan:

- dokumenterade serviceförändringar,
- observerat nuläge i tillhandahållna data,
- reproducerbara GIS-härledningar,
- uppgifter som återstår att verifiera,
- hypoteser som ska prövas i fortsatt analys eller i Fas 2.

Fas 1 är en skrivbords- och GIS-analys. Den ska inte framställa lokala konsekvenser, orsaker eller framtida aktörsåtaganden som fastställda utan en daterad källa. Djupintervjuerna hör enligt uppdragsbeskrivningen huvudsakligen till Fas 2.

## Källor som denna specifikation bygger på

- `karin_lovgren_dalarna/rawdata/Uppdragsbeskrivning paketleveranser_260326.docx.pdf`
- `karin_lovgren_dalarna/docs/uppstart_2026-07-03.md`
- `karin_lovgren_dalarna/docs/forsta_dataprofil.md`
- `karin_lovgren_dalarna/reports/databehov_paketleveranser_dalarna.qmd`
- `data/raw/Paketvolymer_2024_Dalarna_kommun.xlsx`
- `data/raw/Servicepunkter_2026_Dalarna.xlsx`
- Dalastrategin 2030 – Tillsammans för ett hållbart Dalarna, upplaga 2026

## Evidensnivåer

Varje sakuppgift, händelse, indikator och slutsats ska ha en evidensnivå. Nivån beskriver underlagets styrka, inte hur viktig uppgiften är.

| Kod | Benämning | Definition | Exempel |
|---|---|---|---|
| E0 | Okänt | Uppgiften saknas eller kan inte bedömas. | Datum för ett påstått servicebortfall saknas. |
| E1 | Hypotes | Analytiskt antagande eller möjlig förklaring som ännu inte har belagts. | Samordnade transporter skulle kunna minska fordonskilometer. |
| E2 | Dokumentuppgift | Uppgift finns i uppdragsbeskrivning, anteckning eller annan sekundär källa men är inte sakverifierad. | Bingsjö och By nämns som platser som kommer eller kan komma att stå utan paketleveranser. |
| E3 | Datastödd observation | Uppgift kan direkt observeras eller reproducerbart härledas ur levererad data. Den beskriver datakällan, inte nödvändigtvis dagens verkliga förhållande. | Bingsjö Lanthandel finns som en ensam TVV-rad i 2026-filen. |
| E4 | Primärverifierad | Behörig dataägare, ansvarig aktör eller daterat primärdokument har bekräftat uppgiften. | Paketaktören bekräftar ett stängningsdatum och vilken tjänst som upphörde. |

Komplettera vid behov med `verifieringsstatus`: `ej kontrollerad`, `korsläst`, `bekräftad`, `motsagd` eller `inaktuell`. En E3-observation kan alltså fortfarande vara ej kontrollerad mot aktören.

## Databaslinje och försiktighetsnoter

1. `sp2026` innehåller 487 aktörs-/servicerader men endast 236 unika `kluster_id`. Ett kluster ska behandlas som en fysisk nod och en rad som ett aktörserbjudande vid noden.
2. `Kluster` innehåller 236 innehållsrader. Arbetsbokens använda område sträcker sig längre, men tomma/formaterade rader får inte räknas som kluster.
3. De 13 rader som saknar leveransfrekvens är samtliga `TVV` och typen `Butik (stöd)`. En sådan rad bevisar inte aktiv paketservice.
4. Kommunbefolkning, arbetsställen och avlämningsställen upprepas på servicepunktsraderna och får inte tolkas som lokala omlandstal.
5. Paketvolymerna avser 2024 medan servicepunkterna avser 2026. Kommunal volym får inte fördelas schablonmässigt på enskilda noder utan tydlig märkning som proxy.
6. Källrubriken för paketvolymer anger `tst`. Tolkningen som tusen stycken ska bekräftas med dataägaren innan volymer används i slutliga slutsatser.
7. Koordinaterna behandlas preliminärt som SWEREF 99 TM, EPSG:3006. Koordinatsystem och snapshotdatum ska bekräftas med dataägaren.
8. Frånvaro av en ort eller nod i 2026-filen bevisar inte ett historiskt eller aktuellt servicebortfall.
9. Nulägesdata saknar historiska stängningar, öppettider, kapacitet, faktisk volym per nod och vägrestider.

## Centrala begrepp

- **Fysisk nod:** unik fysisk adress/plats, primärt identifierad med `kluster_id`.
- **Aktörserbjudande:** en aktörs registrerade tjänst vid en fysisk nod.
- **Förändringshändelse:** en daterad eller tidsavgränsad förändring i ett aktörserbjudande vid en nod.
- **Fallgeografi:** verifierat funktionellt omland för exempelvis Bingsjö eller By; inte automatiskt hela kommunen.
- **Riskzon:** område som uppvisar en eller flera separata riskdimensioner. Begreppet innebär inte i sig att bortfall har inträffat.

## Leverabler

### L0. Datamodell, källförteckning och evidenslogg

**Besvarar:** samtliga Fas 1-frågor genom gemensam spårbarhet.

**Innehåll:**

- separat nod-, erbjudande-, händelse-, aktörs- och källtabell,
- beskrivning av nycklar, geografisk nivå, tidsreferens och enhet,
- evidensnivå och verifieringsstatus för varje kritisk uppgift,
- logg över metodval, antaganden och kända databrister.

**Minsta acceptans:** varje publicerad indikator kan spåras till källfält, tidsperiod, geografisk nivå och beräkningsregel.

### L1. Verifierad nulägeskarta över noder och aktörserbjudanden

**Besvarar:** var service finns och vilka aktörer som är observerade nu.

**Innehåll:**

- 236 fysiska noder som huvudlager,
- relaterade aktörer och tjänstetyper per nod,
- antal aktörer, antal tjänstetyper och leveransfrekvens,
- tydlig särredovisning av `TVV`/`Butik (stöd)`,
- kommunal kontext utan att kommunvärden framställs som lokala.

**Minsta acceptans:** gränssnitt och tabeller använder termerna `fysiska noder` och `aktörserbjudanden`; 487 benämns aldrig som 487 geografiska servicealternativ.

### L2. Förändringsregister och förändringskarta

**Besvarar:** vilka geografier som faktiskt har drabbats.

**Innehåll:** en rad per dokumenterad förändring i ett aktörserbjudande vid en fysisk nod, med minst:

- stabilt händelse-, plats-, nod- och erbjudande-id,
- händelsetyp och händelsestatus,
- händelsedatum och datumprecision,
- tjänst, aktör och leveransfrekvens före/efter,
- eventuell ersättningsnod eller ersättningslösning,
- uppgiven orsak separat från analytisk tolkning,
- källa, evidensnivå, verifieringsstatus och nästa kontroll.

**Minsta acceptans:** Bingsjö och By har varsin post även om utfallet är `ej verifierat`; dokumentdatum används inte som händelsedatum när händelsedatum saknas.

### L3. Tillgänglighets- och sårbarhetsatlas

**Besvarar:** vilka geografier som ligger i riskzonen och vad som kännetecknar dem.

Risk ska redovisas som separata dimensioner:

1. verifierat servicebortfall,
2. restid till närmaste fysiska nod,
3. restid till näst närmaste nod,
4. restid till alternativ aktör,
5. beroende av en enda nod eller aktör,
6. operativ robusthet: frekvens, öppettider och kapacitet,
7. behov/exponering: befolkning, äldre, företag och fritidshus,
8. möjlig samordning med andra återkommande flöden.

**Minsta acceptans:** restid beräknas i vägnät från befolknings-/företagsgeografi; raka avstånd märks uttryckligen som preliminära. Ett sammanslaget riskindex publiceras inte innan definitioner, vikter och känslighetsanalys har förankrats.

### L4. Platskort för Bingsjö och By

**Besvarar:** likheter, skillnader, lokal exponering och värden.

Varje kort ska innehålla:

- verifierad platsidentitet och fallgeografi,
- tidslinje för paketservice,
- fysiska noder och aktörserbjudanden,
- närmaste, näst närmaste och alternativa aktör via väg,
- lokal demografi, arbetsställen och fritidshus,
- kommunal paketvolym endast som tydligt märkt kontext,
- beroenden, redundans och andra lokala servicefunktioner,
- lokala/regionala värdehypoteser,
- aktörer, rådighet och öppna verifieringsfrågor,
- separat redovisning av fakta, dokumentuppgifter och hypoteser.

**Minsta acceptans:** korten får inte ange att aktiv paketservice finns eller saknas utan E4-underlag eller tydlig markering att uppgiften är obekräftad.

### L5. Jämförelsetypologi och jämförbara platskort

**Besvarar:** hur det ser ut på andra platser med liknande förutsättningar.

Matchning ska ske på funktionellt omland, inte enbart kommuntyp, med variabler för:

- befolkning, åldersstruktur och täthet,
- avstånd/restid till centralort och alternativ service,
- nod- och aktörsredundans,
- företag och arbetsställen,
- fritidshus och säsongsvariation,
- kollektivtrafik och bilberoende,
- dokumenterad typ av serviceförändring.

**Minsta acceptans:** 3–5 jämförelseplatser per huvudfall med transparent urvalsregel, likheter, skillnader och begränsningar för överförbarhet.

### L6. Aktörs-, mandat- och datamatris

**Besvarar:** vilka aktörer som varit relevanta då, nu och framåt.

Granularitet: en rad per aktör × period × roll × geografi. Minst följande ska dokumenteras:

- observerad eller möjlig roll,
- besluts-, avtals-, finansierings- och genomförandemandat,
- ägda noder, resurser, flöden och data,
- geografiskt ansvars-/verksamhetsområde,
- beroenden, incitament och begränsningar,
- rättslig, avtalsmässig eller strategisk grund,
- kontakt, dialogstatus, källa och verifieringsstatus.

**Minsta acceptans:** `möjlig aktör` skiljs från `verifierad aktör`; mandat lämnas som okänt när källstöd saknas. `TVV` utvecklas inte till ett organisationsnamn eller en paketroll innan det har bekräftats.

### L7. RUS-spårbarhetsmatris och värderam

**Besvarar:** regionala samband samt värden bortom effektivitet och lönsamhet.

**Innehåll:**

- exakt målområde, avsnitt och tryckt sidreferens i Dalastrategin 2030, upplaga 2026,
- kopplingsstyrka: direkt, stark, bidragande eller hypotes,
- kausal länk mellan paketprojektets observation och strategimålet,
- indikator, datakälla, ansvarig aktör, nuläge, önskat läge och begränsning,
- värdedimensioner för likvärdig tillgång, tidsbörda, lokalt näringsliv, mötesplats, attraktivitet, tillit, beredskap och klimat.

**Minsta acceptans:** paketservice beskrivs som en möjlig operationalisering av bredare service- och tillgänglighetsmål, inte som något som uttryckligen nämns i Dalastrategin. Klimatnytta anges som hypotes tills transportarbete, basscenario och alternativscenario har beräknats.

## Verifieringsfrågor – Bingsjö

### Plats och nuläge

1. Är `Bingsjö Lanthandel`, Bingsjö Lambornsvägen 15, rätt fysisk plats för fallstudien?
2. Vilka paketfunktioner finns på platsen idag: utlämning, inlämning, returer, box eller ingen paketfunktion?
3. Vilken aktör tillhandahåller respektive funktion och från vilket datum gäller uppgiften?
4. Vad betyder `TVV` och `Butik (stöd)` i dataägarens klassificering?
5. Varför saknas leveransfrekvens, och ska raden över huvud taget ingå i mått på paketservice?

### Förändring

6. Vilken konkret tjänst har upphört, hotats eller ändrats?
7. Vilken aktör fattade eller kommunicerade beslutet?
8. När meddelades och när genomfördes förändringen? Ange datumprecision.
9. Vilken orsak angavs i primärkällan?
10. Finns skriftligt besked, avtal, e-post eller annan daterad primärkälla?

### Alternativ och konsekvensyta

11. Vilka noder används faktiskt som alternativ och för vilka aktörer/tjänster?
12. Vilka vägrestider gäller till första, andra och alternativa aktör under normala respektive vinterförhållanden?
13. Vilka boende, äldre, företag och fritidshushåll ingår i Bingsjös funktionella omland?
14. Vilka andra funktioner bär lanthandeln, och vilka av dem påverkas om paketfunktionen förändras?
15. Finns säsongsvariation eller företagsbehov som kommunala årsmedel döljer?

## Verifieringsfrågor – By

### Platsidentitet

1. Vilken exakt geografi avses med `By` i uppdragsbeskrivningen: ort, församling, postort eller ett större omland?
2. Vilken punkt eller polygon ska användas i GIS-analysen?
3. Kan platsen förekomma under annan adress, postort eller benämning i aktörernas register?
4. Är frånvaron i 2026-filen korrekt, eller är det en matchnings-/klassificeringsfråga?

### Förändring

5. Vilken fysisk nod, rutt, tjänst och aktör avses i problembeskrivningen?
6. Har service upphört, är den beslutad att upphöra eller bedöms den enbart vara hotad?
7. När meddelades respektive genomfördes förändringen?
8. Vilken primärkälla styrker status, datum och angiven orsak?
9. Har en ersättningslösning införts, och motsvarar den samma funktioner?

### Alternativ och konsekvensyta

10. Vilka noder i eller utanför Avesta kommun används faktiskt av boende och företag?
11. Vilken vägrestid gäller till första, andra och alternativa aktör?
12. Vilka befolknings-, ålders-, företags- och fritidshusdata ska kopplas till fallgeografin?
13. Finns kollektivtrafik eller andra transportflöden som påverkar faktisk nåbarhet?
14. Vilka lokala verksamheter skulle kunna vara nod, och vilket mandat eller avtal skulle krävas?

## Gemensamma acceptanskriterier för Fas 1

Fas 1 kan godkännas när:

- alla 487 erbjudanderader är kopplade till en dokumenterad fysisk nodmodell,
- 236 kluster har kvalitetskontrollerats och `TVV` särredovisas,
- Bingsjö och By har verifierad platsavgränsning och tydlig status för serviceförändringen,
- kända förändringsuppgifter har källa, evidensnivå, datumprecision och verifieringsstatus,
- restid till närmaste, näst närmaste och alternativa aktör har beräknats för relevanta befolknings-/företagsgeografier,
- lokal demografi inte ersätts med upprepade kommunvärden,
- jämförelseplatser har valts med reproducerbar metod,
- aktörers mandat och åtaganden är källbelagda eller markerade som okända,
- RUS-kopplingar har indikator, ansvarig aktör, nuläge, önskat läge och begränsning,
- fakta, reproducerbara härledningar, dokumentuppgifter och hypoteser visas separat,
- slutsatserna uttryckligen beaktar tidsmismatchen mellan paketvolymer 2024 och serviceutbud 2026.

## Rekommenderad arbetsordning

1. Fastställ nod-/erbjudandemodell, metadata och evidenslogg.
2. Verifiera platsidentitet och nuläge för Bingsjö och By.
3. Fyll förändringsregistret genom kommun- och aktörskontakter.
4. Lägg till lokal demografi, arbetsställen, fritidshus och vägrestider.
5. Bygg separata riskdimensioner och jämförelsetypologi.
6. Slutför platskort, aktörsmatris och RUS-spårbarhet.
7. Överlämna öppna värde- och konsekvensfrågor till Fas 2:s intervjuer.
