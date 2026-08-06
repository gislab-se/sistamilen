"""Verifieringsbara platskort för prioriterade fall."""

import pandas as pd
import streamlit as st

from dashboard_data import rank_comparable_deso
from dashboard_ui import (
    format_sv,
    load_deso_bundle,
    load_phase1_bundle,
    make_node_map,
    render_map_legend,
)


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
geojson, deso_population, node_deso, deso_metadata = load_deso_bundle()

st.caption(
    "Platskorten skiljer observerade uppgifter från sådant som måste verifieras. "
    "De är startpunkter för skrivbordsanalys och lokala samtal."
)

place = st.selectbox(
    "Prioriterat platsfall",
    cases["plats"].tolist(),
    key="selected_case",
)
case = cases.loc[cases["plats"].eq(place)].iloc[0]
change = changes.loc[changes["plats"].eq(place)].iloc[0]

st.subheader(f"{place}, {case['kommun']} kommun")
st.info(str(case["status"]), icon=":material/info:")

if pd.notna(case["kopplad_nod"]):
    node_id = int(case["kopplad_nod"])
    node = nodes.loc[nodes["kluster_id"].eq(node_id)].iloc[0]
    node_service = service.loc[service["kluster_id"].eq(node_id)].copy()
    node_column, map_column = st.columns([1, 1.5])
    with node_column:
        with st.container(border=True):
            st.markdown("**Observerat i servicepunktsdata 2026**")
            st.metric("Källdefinierad nod", str(node_id))
            st.metric("Aktörer", format_sv(node["antal_aktorer"]))
            st.metric(
                "Närmaste annan nod",
                f"{format_sv(node['narmaste_annan_nod_km'], 1)} km",
                help="Rakt avstånd, inte vägavstånd eller restid.",
            )
            st.write(f"**Nodnamn:** {node['nodnamn']}")
            st.write(f"**Aktörer:** {node['aktorer']}")
            st.write(f"**Servicetyper:** {node['servicetyper']}")
            if node["leveransfrekvens_saknas"]:
                st.warning("Noden saknar helt känd leveransfrekvens.")
    with map_column:
        with st.container(border=True):
            st.markdown("**Geografiskt läge**")
            with st.container(key="case-map-canvas"):
                render_map_legend(
                    "Observerad nodstatus",
                    [
                        ("Flera aktörer", "#18776D", "dot"),
                        ("En aktör", "#BE5B2F", "dot"),
                        ("Kommungräns", "#303942", "line"),
                    ],
                    "case-map-canvas",
                )
                st.pydeck_chart(
                    make_node_map(nodes.loc[nodes["kluster_id"].eq(node_id)]),
                    height=420,
                    key="case-node-map",
                )
            st.caption("Mörk linje = kommungräns härledd från DeSO 2025.")

    st.dataframe(
        node_service[
            [
                "aktor",
                "ombud",
                "typ_servicepunkt",
                "leveransdagar_per_vecka",
                "adress",
                "postort",
            ]
        ].rename(
            columns={
                "aktor": "Aktör",
                "ombud": "Källnamn",
                "typ_servicepunkt": "Servicetyp",
                "leveransdagar_per_vecka": "Leveransdagar/vecka",
                "adress": "Kanonisk adress",
                "postort": "Postort",
            }
        ),
        hide_index=True,
    )

    deso_context = node_deso.loc[node_deso["kluster_id"].eq(node_id)]
    if not deso_context.empty:
        context = deso_context.iloc[0]
        st.markdown("#### Demografisk områdeskontext från SCB")
        with st.container(horizontal=True):
            st.metric("DeSO 2025", str(context["desokod"]), border=True)
            st.metric(
                "Befolkning 2024",
                format_sv(context["befolkning_2024"]),
                border=True,
            )
            st.metric(
                "Andel 65+",
                f"{context['andel_65_plus_2024']:.1%}".replace(".", ","),
                border=True,
            )
            st.metric(
                "Invånare/km²",
                format_sv(context["befolkning_per_km2_2024"], 1),
                border=True,
            )
            st.metric(
                "Servicenoder i DeSO",
                format_sv(context["antal_servicenoder"]),
                border=True,
            )
        st.caption(
            "Talen avser hela DeSO-området där noden ligger — inte orten, "
            "nodens upptagningsområde eller berörd befolkning vid ett bortfall."
        )
        with st.expander(
            "Preliminära jämförelseområden", on_change="rerun"
        ):
            comparable = rank_comparable_deso(
                deso_population,
                str(context["desokod"]),
                limit=5,
            )
            st.dataframe(
                comparable[
                    [
                        "desokod",
                        "kommun",
                        "befolkning_2024",
                        "befolkning_per_km2_2024",
                        "andel_65_plus_2024",
                        "antal_servicenoder",
                        "likhetsavstand",
                    ]
                ].rename(
                    columns={
                        "desokod": "DeSO",
                        "kommun": "Kommun",
                        "befolkning_2024": "Befolkning",
                        "befolkning_per_km2_2024": "Invånare/km²",
                        "andel_65_plus_2024": "Andel 65+",
                        "antal_servicenoder": "Servicenoder",
                        "likhetsavstand": "Statistiskt avstånd",
                    }
                ),
                hide_index=True,
                column_config={
                    "DeSO": st.column_config.TextColumn(pinned=True),
                    "Andel 65+": st.column_config.NumberColumn(format="percent"),
                    "Invånare/km²": st.column_config.NumberColumn(format="%.1f"),
                    "Statistiskt avstånd": st.column_config.NumberColumn(
                        format="%.2f",
                        help="Lägre värde betyder större likhet i fyra angivna mått.",
                    ),
                },
            )
            st.caption(
                "Förurvalet använder lika vikt på befolkning, täthet, andel 65+ "
                "och antal servicenoder. Det visar statistisk likhet — inte "
                "jämförbar förändringshistoria, vägtillgänglighet eller lokal funktion."
            )
else:
    st.warning(
        "Platsen har ingen exakt match och inga verifierade koordinater i "
        "servicepunktsmaterialet. Den ska inte placeras eller riskklassas genom gissning."
    )

question_column, evidence_column = st.columns(2)
with question_column:
    with st.container(border=True):
        st.markdown("**Frågor som måste besvaras**")
        for question in str(case["fragor"]).split("?"):
            if question.strip():
                st.markdown(f"- {question.strip()}?")

with evidence_column:
    with st.container(border=True):
        st.markdown("**Källäget**")
        st.write(f"**Tidigare service:** {change['tidigare_service']}")
        st.write(f"**Observerat nuläge:** {change['observerat_nulage']}")
        st.write(f"**Ersättning:** {change['ersattning']}")
        st.write(f"**Status:** {change['verifieringsstatus']}")
        st.caption(str(change["anteckning"]))

st.subheader("Förändringsregister")
st.dataframe(
    changes,
    hide_index=True,
    column_config={
        "fall_id": st.column_config.TextColumn("Fall-ID", pinned=True),
        "kallreferens": st.column_config.TextColumn("Källreferens"),
    },
)
st.download_button(
    ":material/download: Ladda ner förändringsregister",
    data=changes.to_csv(index=False).encode("utf-8-sig"),
    file_name="forandringsregister.csv",
    mime="text/csv",
    type="tertiary",
)

actor_expander = st.expander("Aktörs- och ansvarsmatris", on_change="rerun")
if actor_expander.open:
    with actor_expander:
        st.warning(
            "Formellt ansvar är ännu inte fastställt. Tabellen är ett "
            "intervju- och verifieringsunderlag."
        )
        st.dataframe(actors, hide_index=True)
        st.download_button(
            ":material/download: Ladda ner aktörsmatris",
            data=actors.to_csv(index=False).encode("utf-8-sig"),
            file_name="aktorsmatris.csv",
            mime="text/csv",
            type="tertiary",
        )
