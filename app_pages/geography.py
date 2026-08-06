"""Geografiska underlagslager från SCB för analysflödena."""

import pandas as pd
import streamlit as st

from dashboard_ui import (
    load_deso_bundle,
    load_phase1_bundle,
    load_place_area_bundle,
    make_deso_map,
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
geojson, population, node_crosswalk, metadata = load_deso_bundle()
place_areas, place_metadata = load_place_area_bundle()

st.caption(
    "Underlagsvy med officiella DeSO 2025, befolkning 2024 och historiska "
    "platslager från SCB, kopplade till servicenätet 2026. För "
    "tillgänglighetsberäkningar används i första hand 1 km-rutor."
)

municipalities = sorted(population["kommun"].dropna().unique().tolist())
selected_municipalities = st.multiselect(
    "Kommuner",
    municipalities,
    default=municipalities,
    key="deso_municipalities",
)
if not selected_municipalities:
    st.warning("Välj minst en kommun.")
    st.stop()

metric_options = {
    "Befolkning": ("befolkning_2024", "Befolkning 2024"),
    "Befolkningstäthet": (
        "befolkning_per_km2_2024",
        "Invånare per km² 2024",
    ),
    "Andel 65 år eller äldre": (
        "andel_65_plus_2024",
        "Andel 65+ 2024",
    ),
    "Servicenoder": ("antal_servicenoder", "Servicenoder 2026"),
}
metric_name = st.segmented_control(
    "Kartmått",
    list(metric_options),
    default="Befolkningstäthet",
    required=True,
    key="deso_metric",
)
metric, metric_label = metric_options[metric_name]
place_types = st.multiselect(
    "Historiska platslager från SCB",
    ["Tätort", "Småort", "Fritidshusområde"],
    default=["Tätort"],
    help=(
        "Senaste publicerade lager i WFS: tätort/småort 2023 och "
        "fritidshusområde 2020. De är strukturunderlag, inte nulägesdata 2026."
    ),
    key="place_area_types",
)

selected_population = population.loc[
    population["kommun"].isin(selected_municipalities)
].copy()
selected_codes = set(selected_population["kommunkod"])
selected_nodes = nodes.loc[nodes["kommun"].isin(selected_municipalities)]
selected_crosswalk = node_crosswalk.loc[
    node_crosswalk["kommun"].isin(selected_municipalities)
]

node_counts = selected_crosswalk.groupby("desokod").size().rename("servicenoder")
area_table = selected_population.merge(
    node_counts, left_on="desokod", right_index=True, how="left"
)
area_table["servicenoder"] = area_table["servicenoder"].fillna(0).astype(int)
population_total = int(area_table["befolkning_2024"].sum())
older_total = int(area_table["befolkning_65_plus_2024"].sum())

with st.container(horizontal=True):
    st.metric("DeSO-områden", f"{len(area_table)}", border=True)
    st.metric("Befolkning 2024", f"{population_total:,}".replace(",", " "), border=True)
    st.metric(
        "Andel 65+",
        f"{older_total / population_total:.1%}".replace(".", ","),
        border=True,
    )
    st.metric("Servicenoder 2026", f"{len(selected_nodes)}", border=True)
    st.metric(
        "DeSO utan observerad nod",
        f"{int(area_table['servicenoder'].eq(0).sum())}",
        help="Detta är en screeninguppgift, inte bevis på att invånare saknar service.",
        border=True,
    )

map_column, rank_column = st.columns([2.2, 1])
with map_column:
    with st.container(border=True):
        st.subheader(metric_label)
        legend_items = [
            (
                f"{metric_label}: lågt → högt",
                "linear-gradient(90deg,#EBEEE0,#1E8F75)",
                "gradient",
            ),
            ("Servicenod", "#5F6873", "dot"),
            ("Kommungräns", "#303942", "line"),
        ]
        place_legend = {
            "Tätort": ("Tätort", "#1E4284", "line"),
            "Småort": ("Småort", "#146952", "line"),
            "Fritidshusområde": ("Fritidshusområde", "#6B3983", "line"),
        }
        legend_items.extend(place_legend[value] for value in place_types)
        with st.container(key="geography-map-canvas"):
            render_map_legend(
                "Kartlager",
                legend_items,
                "geography-map-canvas",
            )
            st.pydeck_chart(
                make_deso_map(
                    geojson,
                    metric,
                    metric_label,
                    nodes=selected_nodes,
                    municipality_codes=selected_codes,
                    place_areas=place_areas,
                    place_types=set(place_types),
                ),
                height=610,
                key="geography-deso-map",
            )
        st.caption(
            "Mörkgrå punkter är källdefinierade adress-/servicenoder. "
            "DeSO-färgen klipps vid 5:e och 95:e percentilen för läsbarhet. "
            "Mörk linje = kommungräns. Blå kontur = tätort, grön = småort, "
            "lila = fritidshusområde."
        )

with rank_column:
    with st.container(border=True):
        st.subheader("Högsta värden i valt mått")
        ranked = area_table.nlargest(18, metric)[
            ["desokod", "kommun", metric]
        ].copy()
        if metric.startswith("andel_"):
            ranked[metric] *= 100
        ranked = ranked.rename(
            columns={
                "desokod": "DeSO",
                "kommun": "Kommun",
                metric: metric_label,
            }
        )
        st.bar_chart(
            ranked,
            x="DeSO",
            y=metric_label,
            horizontal=True,
            sort=f"-{metric_label}",
            color="#287b73",
            height=510,
        )
        st.caption(
            "Diagrammet sorterar endast det valda råvärdet. Det är inte en "
            "prioritering eller riskklassning och tar inte hänsyn till avstånd."
        )

st.subheader("DeSO-tabell")
display = area_table[
    [
        "desokod",
        "kommun",
        "befolkning_2024",
        "befolkning_65_plus_2024",
        "andel_65_plus_2024",
        "servicenoder",
    ]
].rename(
    columns={
        "desokod": "DeSO",
        "kommun": "Kommun",
        "befolkning_2024": "Befolkning 2024",
        "befolkning_65_plus_2024": "Befolkning 65+",
        "andel_65_plus_2024": "Andel 65+",
        "servicenoder": "Servicenoder 2026",
    }
)
st.dataframe(
    display.sort_values(["Kommun", "DeSO"]),
    hide_index=True,
    column_config={
        "DeSO": st.column_config.TextColumn(pinned=True),
        "Befolkning 2024": st.column_config.NumberColumn(format="%d"),
        "Befolkning 65+": st.column_config.NumberColumn(format="%d"),
        "Andel 65+": st.column_config.NumberColumn(format="percent"),
        "Servicenoder 2026": st.column_config.NumberColumn(format="%d"),
    },
)
st.download_button(
    ":material/download: Ladda ner DeSO-tabell",
    data=display.to_csv(index=False).encode("utf-8-sig"),
    file_name="deso_befolkning_servicenoder_dalarna.csv",
    mime="text/csv",
    type="tertiary",
)

with st.expander("Tolkning, källa och avgränsning", on_change="rerun"):
    st.markdown(
        """
        - Ett DeSO är ett statistiskt område, inte automatiskt ett upptagningsområde
          för en servicepunkt.
        - 1 km-rutor är normalt bättre som startpunkter för tillgänglighets- och
          bortfallsberäkning. DeSO används för demografisk kontext, officiell
          summering och kommunikation.
        - Befolkningen gäller 2024 och noderna är en nulägesfil för 2026. Kartan
          visar samlokalisering, inte orsak eller förändring.
        - Områden utan nod kan ha nära service på andra sidan DeSO- eller
          kommungränsen. Nästa analyssteg är därför vägnätsbaserad restid till
          första, andra och alternativ aktör.
        - 65+ är summan av SCB:s grupper 65–69, 70–74, 75–79 och 80+.
        - Tätort och småort avser 2023. Fritidshusområde avser 2020 och visar
          endast områdesgeometri — fältet är en kod, inte antal fritidshus.
          Småorts- och fritidshuslagren saknar namn i WFS-uttaget.
        """
    )
    st.write(
        f"**Hämtad:** {metadata['retrieved_at_utc']} · "
        f"**Geometri:** {metadata['geometry']['source']} · "
        f"**Befolkning:** {metadata['population']['source']}"
    )
    st.write(
        "**Platslager:** "
        + ", ".join(
            f"{layer['omradestyp']} {layer['reference_year']} "
            f"({layer['feature_count']} objekt)"
            for layer in place_metadata["layers"]
        )
    )
    st.link_button(
        ":material/open_in_new: SCB:s befolkningstabell",
        "https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BE__BE0101__BE0101Y/FolkmDesoAldKon/",
        type="tertiary",
    )
