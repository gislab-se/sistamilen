"""Regional överblick över källdata och fysisk servicenätsstruktur."""

import streamlit as st

from dashboard_ui import (
    ACTOR_SERVICE_COLOR,
    DALARNA_MUNICIPALITY_NAMES,
    NODE_TOTAL_COLOR,
    format_sv,
    load_phase1_bundle,
    load_phase1_status_bundle,
    load_population_grid_bundle,
    make_node_map,
    municipality_offer_node_counts,
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
status, rus = load_phase1_status_bundle()
_, population_grid, _ = load_population_grid_bundle()

st.caption(
    "Regional lägesbild · observerat servicenät 2026, kommunala paketvolymer "
    "2024 och SCB:s rutbefolkning 2025."
)

municipality_options = ["Hela Dalarna", *sorted(nodes["kommun"].dropna().unique())]
selected_municipality = st.selectbox(
    "Geografiskt urval",
    municipality_options,
    key="overview-municipality",
    persist_state="session",
)
if selected_municipality == "Hela Dalarna":
    selected_packages = packages
    selected_service = service
    selected_nodes = nodes
    selected_profile = profile
    selected_population = population_grid
    selected_codes = None
    scope_label = "Dalarna"
else:
    selected_packages = packages.loc[packages["kommun"].eq(selected_municipality)]
    selected_service = service.loc[service["kommun"].eq(selected_municipality)]
    selected_nodes = nodes.loc[nodes["kommun"].eq(selected_municipality)]
    selected_profile = profile.loc[profile["kommun"].eq(selected_municipality)]
    selected_population = population_grid.loc[
        population_grid["kommun"].eq(selected_municipality)
    ]
    selected_codes = {
        code
        for code, name in DALARNA_MUNICIPALITY_NAMES.items()
        if name == selected_municipality
    }
    scope_label = f"{selected_municipality} kommun"

with st.container(horizontal=True):
    st.metric(
        "Befolkning 2025",
        format_sv(selected_population["befolkning_2025"].sum()),
        help="Summerad befolkning i SCB:s befolkade 1 × 1 km-rutor.",
        border=True,
    )
    st.metric("Adress-/servicenoder", format_sv(len(selected_nodes)), border=True)
    st.metric(
        "Aktörstjänster",
        format_sv(len(selected_service)),
        help="En fysisk nod kan ha flera aktörsrader.",
        border=True,
    )
    st.metric(
        "Paketvolym 2024",
        f"{format_sv(selected_packages['total_paket_tusen'].sum() / 1_000, 2)} mn",
        help="Paketbrev, B2C, C2X och B2B; källan anges i tusental.",
        border=True,
    )

map_column, count_column = st.columns([2, 1])
with map_column:
    with st.container(border=True):
        st.subheader(f"Fysiskt servicenät – {scope_label}")
        with st.container(key="overview-map-canvas"):
            render_map_legend(
                "Observerad nodstatus",
                [
                    ("Flera aktörer", "#18776D", "dot"),
                    ("En aktör", "#BE5B2F", "dot"),
                    ("Kommungräns", "#303942", "line"),
                ],
                "overview-map-canvas",
            )
            st.pydeck_chart(
                make_node_map(selected_nodes, selected_codes),
                height=560,
                key="overview-node-map",
            )
        st.caption(
            "Kommungränsen är härledd från DeSO 2025. Nodfärgen beskriver "
            "observerad aktörsbredd och mäter inte ensam faktisk sårbarhet."
        )

with count_column:
    with st.container(border=True):
        st.subheader("Fysiska servicenoder och aktörstjänster")
        counts = municipality_offer_node_counts(selected_service, selected_nodes)
        municipality_order = counts.sort_values(
            "Aktörstjänster", ascending=False
        )["Kommun"].tolist()
        counts_long = counts.melt(
            id_vars="Kommun",
            value_vars=["Adress-/servicenoder", "Aktörstjänster"],
            var_name="Analysenhet",
            value_name="Antal",
        )
        st.vega_lite_chart(
            counts_long,
            {
                "mark": {"type": "bar", "cornerRadiusEnd": 2},
                "encoding": {
                    "y": {
                        "field": "Kommun",
                        "type": "nominal",
                        "sort": municipality_order,
                        "title": None,
                    },
                    "x": {
                        "field": "Antal",
                        "type": "quantitative",
                        "title": "Antal",
                    },
                    "yOffset": {
                        "field": "Analysenhet",
                        "type": "nominal",
                        "sort": ["Adress-/servicenoder", "Aktörstjänster"],
                    },
                    "color": {
                        "field": "Analysenhet",
                        "type": "nominal",
                        "scale": {
                            "domain": [
                                "Adress-/servicenoder",
                                "Aktörstjänster",
                            ],
                            "range": [NODE_TOTAL_COLOR, ACTOR_SERVICE_COLOR],
                        },
                        "legend": {"title": None, "orient": "bottom"},
                    },
                    "tooltip": [
                        {"field": "Kommun", "type": "nominal"},
                        {"field": "Analysenhet", "type": "nominal"},
                        {"field": "Antal", "type": "quantitative"},
                    ],
                },
            },
            height=500 if selected_municipality == "Hela Dalarna" else 180,
        )
        st.caption(
            f"{format_sv(len(selected_service))} rader beskriver tjänsteerbjudanden "
            f"vid {format_sv(len(selected_nodes))} källdefinierade "
            "adress-/servicenoder i urvalet."
        )

st.subheader("Fas 1 i korthet")
started_mask = status["status"].isin(["Påbörjad", "Påbörjad screening", "Delvis"])
verified_cases = int(changes["verifieringsstatus"].eq("Verifierad").sum())
with st.container(horizontal=True):
    st.metric(
        "Påbörjade eller delvisa frågor",
        f"{int(started_mask.sum())} av {len(status)}",
        border=True,
    )
    st.metric(
        "Verifierade förändringsfall",
        format_sv(verified_cases),
        help="Bingsjö och By är verifieringsfall tills datum, beslut och ersättning har styrkts.",
        border=True,
    )
    st.metric(
        "RUS-kopplingar",
        format_sv(len(rus)),
        help="Preliminära, spårbara kopplingar som återstår att validera med ansvariga funktioner.",
        border=True,
    )

with st.container(border=True):
    st.markdown("**Viktigaste gapen före en färdig Fas 1**")
    gap_table = status[["fas1_fraga", "status", "kritiskt_gap"]].rename(
        columns={
            "fas1_fraga": "Uppdragsfråga",
            "status": "Evidensläge",
            "kritiskt_gap": "Kritiskt gap",
        }
    )
    st.dataframe(
        gap_table,
        hide_index=True,
        column_config={
            "Uppdragsfråga": st.column_config.TextColumn(pinned=True),
            "Evidensläge": st.column_config.TextColumn(width="small"),
            "Kritiskt gap": st.column_config.TextColumn(width="large"),
        },
    )
    st.caption(
        "Prioritet: verifiera förändringsfallen, ersätt fågelvägsavstånd med "
        "vägnätsbaserad restid och förankra risktrösklar, ansvar samt RUS-kopplingar."
    )

with st.expander("Datatolkning", on_change="rerun") as interpretation:
    if interpretation.open:
        st.markdown(
            f"""
            Dashboarden läser från `{data_directory}`.

            - **Observerat:** paketvolymerna finns endast per kommun och avser 2024.
            - **Observerat:** servicenätet avser 2026 och visar nuläge, inte dokumenterade stängningar.
            - **Beräknat:** rutbefolkningen summeras från SCB:s befolkade 1 km-rutor 2025.
            - `kluster_id`, adress-ID och koordinatpar ger {len(nodes)} källdefinierade noder.
            - Sex noder ligger närmare än 25 meter från en annan separat källnod och är
              flaggade för manuell kvalitetskontroll, inte automatiskt sammanslagna.
            """
        )
