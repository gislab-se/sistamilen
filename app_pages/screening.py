"""Transparent kommunal screening utan sammanslaget riskindex."""

import pandas as pd
import streamlit as st

from dashboard_ui import load_phase1_bundle


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
    "Beräknad kommunal screening, version 1. Fyra relativa signaler visas var "
    "för sig; de stödjer urval för vidare granskning och är inte ett riskindex."
)

municipalities = sorted(profile["kommun"].dropna().tolist())
selected_municipalities = st.multiselect(
    "Kommuner i jämförelsen",
    municipalities,
    default=municipalities,
    key="screening_municipalities",
)
selected = profile.loc[profile["kommun"].isin(selected_municipalities)].copy()
if selected.empty:
    st.warning("Välj minst en kommun.")
    st.stop()

dimension_map = {
    "Efterfrågetryck": "screening_efterfragetryck",
    "Nodgleshet (nod–nod-proxy)": "screening_nodgleshet",
    "Aktörsberoende": "screening_aktorberoende",
    "Leveransunderlag (proxy)": "screening_leveransunderlag",
}
dimension = st.segmented_control(
    "Screeningdimension",
    list(dimension_map),
    default="Efterfrågetryck",
    required=True,
    key="screening_dimension",
)
score_column = dimension_map[dimension]

ranked = selected.sort_values(score_column, ascending=False)
leader = ranked.iloc[0]
with st.container(horizontal=True):
    st.metric(
        "Högst relativ signal",
        leader["kommun"],
        help=(
            f"Högst percentilvärde för {dimension.lower()} bland kommunerna som "
            "visas. Percentilen är alltid beräknad mot samtliga 15 kommuner."
        ),
        border=True,
    )
    st.metric(
        "Servicenoder i urvalet",
        f"{int(selected['servicenoder'].sum())}",
        border=True,
    )
    st.metric(
        "Aktörstjänster i urvalet",
        f"{int(selected['aktorstjanster'].sum())}",
        border=True,
    )

st.caption(
    "Kommunurvalet styr vad som visas, men ändrar inte referensgruppen: alla "
    "percentiler är beräknade mot Dalarnas 15 kommuner."
)

rank_column, scatter_column = st.columns([1, 1.4])
with rank_column:
    with st.container(border=True):
        st.subheader(f"Relativ signal: {dimension.lower()}")
        bar_data = ranked[["kommun", score_column]].rename(
            columns={"kommun": "Kommun", score_column: "Percentil (0–100)"}
        )
        st.bar_chart(
            bar_data,
            x="Kommun",
            y="Percentil (0–100)",
            horizontal=True,
            sort="-Percentil (0–100)",
            color="#b65b2f",
            height=440,
        )

with scatter_column:
    with st.container(border=True):
        st.subheader("Efterfrågetryck och fysisk nodtäthet")
        scatter = selected.rename(
            columns={
                "kommun": "Kommun",
                "kommuntyp": "Kommuntyp",
                "servicenoder_per_10000_inv": "Noder per 10 000 invånare",
                "b2c_tusen_per_servicenod": "B2C per nod (tusen)",
                "total_paket_tusen": "Total paketvolym (tusen)",
            }
        )
        st.scatter_chart(
            scatter,
            x="Noder per 10 000 invånare",
            y="B2C per nod (tusen)",
            color="Kommuntyp",
            size="Total paketvolym (tusen)",
            height=440,
        )
        st.caption(
            "Paketvolymen är ett kommunalt 2024-genomsnitt; bubblan säger "
            "inte vilken nod som har belastningen."
        )

st.subheader("Alla dimensioner")
dimension_long = selected[
    ["kommun", *dimension_map.values()]
].rename(
    columns={
        "kommun": "Kommun",
        **{value: label for label, value in dimension_map.items()},
    }
).melt(id_vars="Kommun", var_name="Dimension", value_name="Percentil (0–100)")
st.bar_chart(
    dimension_long,
    x="Kommun",
    y="Percentil (0–100)",
    color="Dimension",
    stack=False,
    height=410,
)

screening_table = selected[
    [
        "kommun",
        "servicenoder",
        "aktorstjanster",
        "b2c_tusen_per_servicenod",
        "servicenoder_per_10000_inv",
        "median_narmaste_nod_km",
        "andel_enaktor_noder",
        "median_leveransdagar_per_vecka",
        *dimension_map.values(),
    ]
].rename(
    columns={
        "kommun": "Kommun",
        "servicenoder": "Noder",
        "aktorstjanster": "Aktörstjänster",
        "b2c_tusen_per_servicenod": "B2C/nod (tusen)",
        "servicenoder_per_10000_inv": "Noder/10 000 inv.",
        "median_narmaste_nod_km": "Median nodavstånd (km)",
        "andel_enaktor_noder": "Andel enaktörsnoder",
        "median_leveransdagar_per_vecka": "Median leveransdagar",
        **{value: label for label, value in dimension_map.items()},
    }
)
st.dataframe(
    screening_table,
    hide_index=True,
    column_config={
        "Kommun": st.column_config.TextColumn(pinned=True),
        "B2C/nod (tusen)": st.column_config.NumberColumn(format="%.1f"),
        "Noder/10 000 inv.": st.column_config.NumberColumn(format="%.1f"),
        "Median nodavstånd (km)": st.column_config.NumberColumn(format="%.1f"),
        "Andel enaktörsnoder": st.column_config.NumberColumn(format="percent"),
        **{
            label: st.column_config.ProgressColumn(min_value=0, max_value=100)
            for label in dimension_map
        },
    },
)

method = st.expander("Metod och begränsningar", on_change="rerun")
if method.open:
    with method:
        st.markdown(
            """
            Varje dimension är en percentilrankning bland Dalarnas 15 kommuner:

            - **Efterfrågetryck:** B2C-volym 2024 per adress-/servicenod 2026.
            - **Nodgleshet (proxy):** median rakt avstånd från en nod till närmaste
              annan nod. Måttet beskriver nodernas inbördes spridning, inte
              befolkningens tillgänglighet, och ska ersättas av rutbaserade mått.
            - **Aktörsberoende:** andelen noder med endast en observerad aktör.
            - **Leveransunderlag (proxy):** låg medianleveransfrekvens och andel
              noder utan känd frekvens. Måttet har låg variation och ska inte
              tolkas som faktisk leveranskvalitet.

            Måtten är relativa, använder olika år och saknar ännu historiska
            stängningar och vägnätsbaserade restider. DeSO finns under
            *Underlag → Geografiska lager*, men ingår ännu inte i rankningen.
            Måtten ska därför inte summeras eller etiketteras som faktisk risk.
            """
        )
