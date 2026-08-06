"""Utforskning av det fysiska servicenätet och dess redundans."""

import pandas as pd
import streamlit as st

from dashboard_ui import (
    ACTOR_SERVICE_COLOR,
    SERVICE_TYPE_COLOR,
    format_sv,
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

st.caption(
    "Observerat servicenät 2026. Noderna följer källans klusterindelning; "
    "närhetsmåtten är raka avstånd och ännu inte restid för befolkningen."
)

with st.container(border=True):
    st.markdown("**Urval**")
    filter_columns = st.columns(3)
    with filter_columns[0]:
        municipalities = sorted(nodes["kommun"].dropna().unique().tolist())
        selected_municipalities = st.multiselect(
            "Kommun",
            municipalities,
            default=municipalities,
            key="network_municipalities",
        )
    with filter_columns[1]:
        actor_options = sorted(service["aktor"].dropna().unique().tolist())
        selected_actors = st.multiselect(
            "Noden innehåller någon av aktörerna",
            actor_options,
            default=actor_options,
            key="network_actors",
        )
    with filter_columns[2]:
        service_type_options = sorted(
            service["typ_servicepunkt"].dropna().unique().tolist()
        )
        selected_service_types = st.multiselect(
            "Servicetyp",
            service_type_options,
            default=service_type_options,
            key="network_service_types",
        )

selected_service = service.loc[
    service["kommun"].isin(selected_municipalities)
    & service["aktor"].isin(selected_actors)
    & service["typ_servicepunkt"].isin(selected_service_types)
].copy()
actor_node_ids = selected_service["kluster_id"].unique()
selected_nodes = nodes.loc[
    nodes["kommun"].isin(selected_municipalities)
    & nodes["kluster_id"].isin(actor_node_ids)
].copy()

if selected_nodes.empty:
    st.warning("Inga adress-/servicenoder matchar urvalet.")
    st.stop()

with st.container(horizontal=True):
    st.metric("Noder", format_sv(len(selected_nodes)), border=True)
    st.metric(
        "Enaktörsnoder",
        format_sv(int(selected_nodes["en_aktor"].sum())),
        help="Noder som bara har en observerad aktör i 2026 års källdata.",
        border=True,
    )
    st.metric(
        "Multiaktörsnoder",
        format_sv(int((~selected_nodes["en_aktor"]).sum())),
        border=True,
    )
    st.metric(
        "Median till annan nod",
        f"{format_sv(selected_nodes['narmaste_annan_nod_km'].median(), 1)} km",
        help=(
            "Rakt avstånd till närmaste nod i hela observerade nätet, även när "
            "ett aktörs- eller servicetypsfilter används. Inte restid eller "
            "avstånd från bostäder."
        ),
        border=True,
    )

map_column, distance_column = st.columns([2, 1])
with map_column:
    with st.container(border=True):
        st.subheader("Noder och observerad aktörsbredd")
        with st.container(key="network-map-canvas"):
            render_map_legend(
                "Observerad nodstatus",
                [
                    ("Flera aktörer", "#18776D", "dot"),
                    ("En aktör", "#BE5B2F", "dot"),
                    ("Kommungräns", "#303942", "line"),
                ],
                "network-map-canvas",
            )
            st.pydeck_chart(
                make_node_map(selected_nodes),
                height=560,
                key="network-node-map",
            )
        st.caption(
            "Grön = flera observerade aktörer, orange = en aktör. "
            "Mörk linje = kommungräns härledd från DeSO 2025. Färgen beskriver "
            "nodens fullständiga aktörsbredd i källan, inte bara det filtrerade urvalet."
        )

with distance_column:
    with st.container(border=True):
        st.subheader("Nodgleshet per kommun")
        distance_summary = (
            selected_nodes.groupby("kommun", as_index=False)
            .agg(
                Median=("narmaste_annan_nod_km", "median"),
                Maximum=("narmaste_annan_nod_km", "max"),
            )
            .rename(columns={"kommun": "Kommun"})
        )
        distance_long = distance_summary.melt(
            id_vars="Kommun", var_name="Mått", value_name="Rakt avstånd (km)"
        )
        st.bar_chart(
            distance_long,
            x="Kommun",
            y="Rakt avstånd (km)",
            color="Mått",
            horizontal=True,
            stack=False,
            sort="-Rakt avstånd (km)",
            height=500,
        )
        st.caption(
            "Avståndet är beräknat mot hela servicenätet. Filtren styr vilka "
            "noder som sammanfattas, inte vilka alternativa noder som räknas."
        )

st.subheader("Aktörer och servicetyper i urvalet")
actor_column, type_column = st.columns(2)
with actor_column:
    with st.container(border=True):
        st.markdown("**Aktörstjänster per aktör**")
        actor_counts = (
            selected_service.groupby("aktor", as_index=False)
            .size()
            .rename(columns={"aktor": "Aktör", "size": "Aktörstjänster"})
        )
        st.bar_chart(
            actor_counts,
            x="Aktör",
            y="Aktörstjänster",
            sort="-Aktörstjänster",
            color=ACTOR_SERVICE_COLOR,
            height=330,
        )

with type_column:
    with st.container(border=True):
        st.markdown("**Aktörstjänster per servicetyp**")
        type_counts = (
            selected_service.groupby("typ_servicepunkt", as_index=False)
            .size()
            .rename(
                columns={"typ_servicepunkt": "Servicetyp", "size": "Aktörstjänster"}
            )
        )
        st.bar_chart(
            type_counts,
            x="Servicetyp",
            y="Aktörstjänster",
            sort="-Aktörstjänster",
            color=SERVICE_TYPE_COLOR,
            height=330,
        )
st.caption(
    "En aktörstjänst är en aktörs erbjudande vid en fysisk nod. Därför kan "
    "antalet aktörstjänster vara större än antalet noder."
)

st.subheader("Nodregister")
node_table = selected_nodes[
    [
        "nodnamn",
        "postort",
        "kommun",
        "antal_aktorer",
        "aktorer",
        "servicetyper",
        "median_leveransdagar_per_vecka",
        "narmaste_annan_nod_km",
        "narmaste_nod_med_annan_aktor_km",
        "qa_nara_annan_nod_under_25m",
        "kluster_id",
    ]
].rename(
    columns={
        "nodnamn": "Nod",
        "postort": "Postort",
        "kommun": "Kommun",
        "antal_aktorer": "Antal aktörer",
        "aktorer": "Aktörer",
        "servicetyper": "Servicetyper",
        "median_leveransdagar_per_vecka": "Median leveransdagar/vecka",
        "narmaste_annan_nod_km": "Närmaste annan nod (km)",
        "narmaste_nod_med_annan_aktor_km": "Annan aktör (km)",
        "qa_nara_annan_nod_under_25m": "QA <25 m",
        "kluster_id": "Kluster-ID",
    }
)
st.dataframe(
    node_table,
    hide_index=True,
    column_config={
        "Nod": st.column_config.TextColumn(pinned=True),
        "Antal aktörer": st.column_config.NumberColumn(format="%d"),
        "Median leveransdagar/vecka": st.column_config.NumberColumn(format="%.1f"),
        "Närmaste annan nod (km)": st.column_config.NumberColumn(format="%.1f"),
        "Annan aktör (km)": st.column_config.NumberColumn(format="%.1f"),
        "QA <25 m": st.column_config.CheckboxColumn(
            help="Separata källnoder som bör kontrolleras manuellt."
        ),
    },
)

st.download_button(
    ":material/download: Ladda ner nodurval",
    data=node_table.to_csv(index=False).encode("utf-8-sig"),
    file_name="servicenoder_urval.csv",
    mime="text/csv",
    type="tertiary",
)
