# Första dataprofil: paketvolymer och servicepunkter

Skapad från:

- `rawdata/Paketvolymer_2024_Dalarna_kommun.xlsx`
- `rawdata/Servicepunkter_2026_Dalarna.xlsx`

Paketvolymerna i källfilen anges i tusental. Profilen är en första screening på kommunnivå och ska inte tolkas som ett färdigt riskindex.

## Topp 5: B2C-volym per servicepunkt

| kommun | b2c_tusen | servicepunkter | b2c_tusen_per_servicepunkt | kommuntyp |
| --- | --- | --- | --- | --- |
| Smedjebacken | 155.36 | 12 | 12.95 | 4. Landsbygdskommuner nära större städer |
| Hedemora | 225.16 | 22 | 10.23 | 4. Landsbygdskommuner nära större städer |
| Falun | 903.86 | 91 | 9.93 | 2. Täta kommuner nära större städer |
| Säter | 156.87 | 16 | 9.80 | 4. Landsbygdskommuner nära större städer |
| Ludvika | 390.81 | 41 | 9.53 | 2. Täta kommuner nära större städer |

## Topp 5: preliminär screeningpoäng

Screeningpoängen väger samman hög B2C-volym per servicepunkt, låg servicepunktstäthet per invånare och låg medianleveransfrekvens.

| kommun | preliminar_screeningpoang | b2c_tusen_per_servicepunkt | servicepunkter_per_10000_inv | median_leveransdagar_per_vecka | kommuntyp |
| --- | --- | --- | --- | --- | --- |
| Smedjebacken | 0.87 | 12.95 | 11.12 | 5.00 | 4. Landsbygdskommuner nära större städer |
| Hedemora | 0.79 | 10.23 | 14.47 | 5.00 | 4. Landsbygdskommuner nära större städer |
| Säter | 0.76 | 9.80 | 14.29 | 5.00 | 4. Landsbygdskommuner nära större städer |
| Falun | 0.72 | 9.93 | 15.23 | 5.00 | 2. Täta kommuner nära större städer |
| Mora | 0.65 | 9.21 | 15.12 | 5.00 | 3. Täta kommuner avlägset belägna |

## Lägst servicepunktstäthet per 10 000 invånare

| kommun | servicepunkter | befolkning_kn | servicepunkter_per_10000_inv | kommuntyp |
| --- | --- | --- | --- | --- |
| Smedjebacken | 12 | 10795 | 11.12 | 4. Landsbygdskommuner nära större städer |
| Säter | 16 | 11194 | 14.29 | 4. Landsbygdskommuner nära större städer |
| Hedemora | 22 | 15206 | 14.47 | 4. Landsbygdskommuner nära större städer |
| Mora | 31 | 20497 | 15.12 | 3. Täta kommuner avlägset belägna |
| Falun | 91 | 59770 | 15.23 | 2. Täta kommuner nära större städer |

## Att kontrollera före tolkning

- Om servicepunktskoordinaterna ska tolkas som SWEREF 99 TM eller annat koordinatsystem.
- Om paketvolymerna ska behandlas som årsvolym i tusental för samtliga kategorier.
- Om varje rad i `sp2026` ska räknas som en separat servicepunkt, eller om vissa rader bör klustras innan nyckeltal tas fram.
- Om kommunnivå är tillräckligt för första prioritering, eller om analysen snabbt bör gå över till postort, kluster eller restidsområden.
