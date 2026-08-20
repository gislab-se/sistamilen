# Open source-alternativ till Streamlit

För det här projektet är Shiny ett bra första test eftersom R, Shiny, Leaflet, DT, Plotly, readxl och sf redan finns installerade lokalt.

## Bra kandidater

| Ramverk | Språk | Passar bäst när | Kommentar |
| --- | --- | --- | --- |
| Shiny | R eller Python | Analysappar, geodata, tabeller, reaktiva filter | Mycket starkt om datalogiken redan finns i R eller om man vill använda Leaflet/sf enkelt. |
| Dash | Python, R, Julia | Plotly-tunga dashboards och produktionsnära analysappar | Mer callback-orienterat än Streamlit; bra kontroll över layout och interaktion. |
| Panel | Python | Notebooknära dashboards, HoloViz, Bokeh, datavetenskapliga arbetsflöden | Flexibelt och bra för mer avancerade Python-visualiseringar. |
| NiceGUI | Python | Snabba interna verktyg med modern UI-känsla | Mer allmänt UI-ramverk än ren data-dashboard. |
| Solara | Python | React-liknande appar i ren Python, ofta Jupyternära | Bra om man vill bygga komponentbaserat utan JavaScript. |
| Voilà | Python/Jupyter | Dela notebooks som webbappar | Bra för notebookflöden, mindre bra för skräddarsydda gränssnitt. |
| Bokeh Server | Python | Interaktiva Bokeh-visualiseringar | Stabilt, men lägre nivå än Streamlit och Panel. |
| Taipy | Python | Dataappar med scenario-/pipeline-logik | Intressant för beslutstöd och processflöden. |

## Rekommendation för projektet

Börja med Shiny för att snabbt få en lokal gränssnittsyta mot befintliga Excel-filer. Om projektet senare ska bli mer Python-centrerat är Dash eller Panel de mest naturliga nästa alternativen.

