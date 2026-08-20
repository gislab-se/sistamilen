"""Startpunkt och navigation för Fas 1-dashboarden."""

import streamlit as st


st.set_page_config(
    page_title="Paketleveranser i Dalarna – Fas 1",
    page_icon=":material/local_shipping:",
    layout="wide",
)

page = st.navigation(
    {
        "": [
            st.Page(
                "app_pages/overview.py",
                title="Lägesbild",
                icon=":material/dashboard:",
                default=True,
            ),
            st.Page(
                "app_pages/network.py",
                title="Servicenät",
                icon=":material/hub:",
            ),
            st.Page(
                "app_pages/simulation.py",
                title="Tillgänglighet och bortfall",
                icon=":material/science:",
            ),
            st.Page(
                "app_pages/screening.py",
                title="Screening",
                icon=":material/analytics:",
            ),
            st.Page(
                "app_pages/cases.py",
                title="Platsfall",
                icon=":material/location_on:",
            ),
            st.Page(
                "app_pages/waste_routes.py",
                title="Sophämtningskarta",
                icon=":material/recycling:",
            ),
        ],
        "Underlag": [
            st.Page(
                "app_pages/geography.py",
                title="Geografiska lager",
                icon=":material/map:",
            ),
            st.Page(
                "app_pages/phase1.py",
                title="Metod och status",
                icon=":material/checklist:",
            ),
        ],
    },
    position="top",
)

st.markdown(f"# {page.icon} {page.title}")
page.run()
