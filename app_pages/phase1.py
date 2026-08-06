"""Metod, källor, RUS-koppling och konkret arbetsbacklog för Fas 1."""

import pandas as pd
import streamlit as st

from dashboard_ui import load_phase1_bundle, load_phase1_status_bundle


(
    packages,
    service,
    nodes,
    profile,
    clusters,
    changes,
    actors,
    cases,
    data_directory,
) = load_phase1_bundle()

status, rus = load_phase1_status_bundle()

st.caption(
    "Sekundär underlagssida för spårbarhet, källor och arbetsordning. Status "
    "betyder evidensläge, inte nedlagd arbetstid."
)

with st.container(border=True):
    st.markdown("**Så ska resultat märkas**")
    st.write(
        "**Observerat** = direkt källuppgift · **Beräknat** = reproducerbart "
        "mått · **Scenario** = hypotetisk förändring · **Ej verifierat** = "
        "kräver bekräftelse · **Datagap** = nödvändigt underlag saknas."
    )

started = status["status"].isin(
    ["Påbörjad", "Påbörjad screening", "Delvis"]
).sum()
with st.container(horizontal=True):
    st.metric("Fas 1-frågor", str(len(status)), border=True)
    st.metric("Påbörjade/delvis", str(int(started)), border=True)
    st.metric(
        "Ej tillräckligt analyserade",
        str(int(len(status) - started)),
        border=True,
    )
    st.metric(
        "Verifierade förändringsfall",
        str(int(changes["verifieringsstatus"].eq("Verifierad").sum())),
        help="Bingsjö och By är ännu verifieringsfall, inte fastställda händelser.",
        border=True,
    )

st.subheader("Läget mot uppdragsbeskrivningen")
st.dataframe(
    status,
    hide_index=True,
    column_config={
        "fas1_fraga": st.column_config.TextColumn("Fas 1-fråga", pinned=True),
        "status": st.column_config.TextColumn("Status"),
        "det_vi_har": st.column_config.TextColumn("Det vi har"),
        "kritiskt_gap": st.column_config.TextColumn("Kritiskt gap"),
        "nasta_leverabel": st.column_config.TextColumn("Nästa leverabel"),
    },
)

st.subheader("Koppling till Dalastrategin 2030")
rus_display = rus[
    [
        "koppling_id",
        "malomrade",
        "rus_avsnitt",
        "rus_sidreferens",
        "kopplingsstyrka",
        "indikator",
        "nulage",
        "onskat_lage",
        "begransning",
        "evidensstatus",
    ]
]
st.dataframe(
    rus_display,
    hide_index=True,
    column_config={
        "koppling_id": st.column_config.TextColumn("ID", pinned=True),
        "malomrade": st.column_config.TextColumn("Målområde"),
        "rus_avsnitt": st.column_config.TextColumn("RUS-avsnitt"),
        "rus_sidreferens": st.column_config.TextColumn("Sida"),
        "kopplingsstyrka": st.column_config.TextColumn("Kopplingsstyrka"),
        "indikator": st.column_config.TextColumn("Indikator"),
        "nulage": st.column_config.TextColumn("Nuläge"),
        "onskat_lage": st.column_config.TextColumn("Önskat läge"),
        "begransning": st.column_config.TextColumn("Begränsning"),
        "evidensstatus": st.column_config.TextColumn("Evidensstatus"),
    },
)
st.caption(
    "Matrisen använder den reviderade Dalastrategin 2030 (2026). "
    "Kopplingarna ska valideras med ansvariga regionala funktioner."
)
st.download_button(
    ":material/download: Ladda ner fullständig RUS-matris",
    data=rus.to_csv(index=False).encode("utf-8-sig"),
    file_name="rus_koppling.csv",
    mime="text/csv",
    type="tertiary",
)

st.subheader("Databeredskap för nästa analyssteg")
data_readiness = pd.DataFrame(
    [
        {
            "Underlag": "SCB DeSO 2025 + befolkning 2024",
            "Läge": "Integrerat",
            "Användning": "Fin geografi, totalbefolkning, 65+ och täthet",
            "Nästa åtgärd": "Definiera funktionella restidsomland",
        },
        {
            "Underlag": "SCB befolkning på 1 km-rutor 2025",
            "Läge": "Integrerat",
            "Användning": "Bortfallssimulering, berörd befolkning och 65+",
            "Nästa åtgärd": "Ersätt fågelvägsavstånd med vägnätsbaserad restid",
        },
        {
            "Underlag": "SCB tätort/småort/fritidshusområde",
            "Läge": "Integrerat",
            "Användning": "Historisk platsstruktur och jämförelsetyp",
            "Nästa åtgärd": "Koppla till funktionella omland; komplettera fritidshusantal separat",
        },
        {
            "Underlag": "NVDB-vägnät och bilrestider",
            "Läge": "Kräver konto/uttag",
            "Användning": "Restid till första, andra och alternativ aktör",
            "Nästa åtgärd": "Beställ Dalarna-uttag i Trafikverkets Lastkajen",
        },
        {
            "Underlag": "Dalatrafik GTFS",
            "Läge": "Kräver Trafiklab-nyckel",
            "Användning": "Närmaste hållplats och vardagsavgångar",
            "Nästa åtgärd": "Skapa API-nyckel och datera ett lokalt snapshot",
        },
        {
            "Underlag": "Serviceförändringar Bingsjö och By",
            "Läge": "Kräver primärverifiering",
            "Användning": "Faktiskt bortfall, tidslinje och ersättningslösning",
            "Nästa åtgärd": "Kontakta kommun, lokal nod och berörda paketaktörer",
        },
    ]
)
st.dataframe(
    data_readiness,
    hide_index=True,
    column_config={
        "Underlag": st.column_config.TextColumn(pinned=True),
        "Läge": st.column_config.TextColumn(),
        "Användning": st.column_config.TextColumn(),
        "Nästa åtgärd": st.column_config.TextColumn(),
    },
)

st.subheader("Arbetsordning till en färdig Fas 1")
work_packages = [
    (
        "1. Verifiera förändringar",
        "Kommuner, aktörer och lokala noder fyller förändringsregistret med datum, beslut och ersättning.",
    ),
    (
        "2. Fördjupa geografi och demografi",
        "DeSO, platsområden och 1 km-rutor är integrerade. Komplettera med arbetsställen, fritidshusantal och funktionella omland.",
    ),
    (
        "3. Beräkna faktisk tillgänglighet",
        "Restid till närmaste och näst närmaste nod/aktör ersätter raka nodavstånd.",
    ),
    (
        "4. Jämför platstyper",
        "Bingsjö och By jämförs med 4–6 orter med liknande geografi och demografi.",
    ),
    (
        "5. Fånga lokala värden",
        "Intervjuer beskriver social funktion, företagsnytta, vardagsresor, beredskap och lokal rådighet.",
    ),
    (
        "6. Validera och leverera",
        "Resultat granskas med kommuner/aktörer och sammanställs i karta, platskort och Fas 1-rapport.",
    ),
]
for title, description in work_packages:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.write(description)

st.download_button(
    ":material/download: Ladda ner Fas 1-status",
    data=status.to_csv(index=False).encode("utf-8-sig"),
    file_name="fas1_status.csv",
    mime="text/csv",
    type="tertiary",
)
