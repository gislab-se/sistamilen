"""Befolkningsviktad tillgänglighetsscreening från 1 km-rutor."""

import numpy as np
import pandas as pd
import streamlit as st

from dashboard_data import (
    aggregate_grid_service_options_by_municipality,
    calculate_grid_service_options,
)
from dashboard_ui import (
    ACCESSIBILITY_HEX,
    DALARNA_MUNICIPALITY_NAMES,
    format_sv,
    load_phase1_bundle,
    load_population_grid_bundle,
    make_screening_grid_map,
    render_map_legend,
)


@st.cache_data(show_spinner="Beräknar rutbaserade servicealternativ …", max_entries=4)
def build_screening_data(
    grid: pd.DataFrame,
    node_data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    options = calculate_grid_service_options(grid, node_data)
    summary = aggregate_grid_service_options_by_municipality(options)
    return options, summary


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
grid_geojson, population_grid, grid_metadata = load_population_grid_bundle()
grid_options, municipality_summary = build_screening_data(population_grid, nodes)

st.caption(
    "Beräknad screening med SCB:s befolkade 1 × 1 km-rutor 2025 och det "
    "observerade servicenätet 2026. Dimensionerna visas var för sig och "
    "summeras inte till ett riskindex."
)

dimension_options = {
    "Första nod": {
        "grid_column": "avstand_forsta_nod_km",
        "summary_column": "befolkningsvagt_forsta_nod_km",
        "score_column": "screening_forsta_nod",
        "label": "Avstånd till närmaste nod",
        "thresholds": (5.0, 10.0, 20.0, 30.0),
        "focus_threshold": 10.0,
        "explanation": "grundläggande geografisk tillgänglighet",
    },
    "Andra nod": {
        "grid_column": "avstand_andra_nod_km",
        "summary_column": "befolkningsvagt_andra_nod_km",
        "score_column": "screening_andra_nod",
        "label": "Avstånd till näst närmaste nod",
        "thresholds": (5.0, 10.0, 20.0, 30.0),
        "focus_threshold": 20.0,
        "explanation": "geografisk redundans om den närmaste noden inte kan användas",
    },
    "Alternativ aktör": {
        "grid_column": "avstand_alternativ_aktor_km",
        "summary_column": "befolkningsvagt_alternativ_aktor_km",
        "score_column": "screening_alternativ_aktor",
        "label": "Avstånd till alternativ aktör",
        "thresholds": (5.0, 10.0, 20.0, 30.0),
        "focus_threshold": 20.0,
        "explanation": "möjlighet att nå minst en aktör som saknas vid närmaste nod",
    },
    "Redundansgap": {
        "grid_column": "redundansgap_km",
        "summary_column": "befolkningsvagt_redundansgap_km",
        "score_column": "screening_redundansgap",
        "label": "Avståndsökning till andra nod",
        "thresholds": (2.0, 5.0, 10.0, 20.0),
        "focus_threshold": 10.0,
        "explanation": "hur mycket längre bort den andra noden ligger än den första",
    },
}

with st.container(border=True):
    filter_column, dimension_column = st.columns([1.4, 1])
    with filter_column:
        municipalities = sorted(grid_options["kommun"].dropna().unique().tolist())
        selected_municipalities = st.multiselect(
            "Kommuner",
            municipalities,
            default=municipalities,
            key="screening-municipalities-v2",
        )
    with dimension_column:
        dimension = st.segmented_control(
            "Screeningdimension",
            list(dimension_options),
            default="Första nod",
            required=True,
            key="screening-dimension-v2",
        )

if not selected_municipalities:
    st.warning("Välj minst en kommun.")
    st.stop()

config = dimension_options[dimension]
grid_column = str(config["grid_column"])
summary_column = str(config["summary_column"])
score_column = str(config["score_column"])
metric_label = str(config["label"])
thresholds = tuple(float(value) for value in config["thresholds"])
focus_threshold = float(config["focus_threshold"])

selected_grid = grid_options.loc[
    grid_options["kommun"].isin(selected_municipalities)
].copy()
selected_summary = municipality_summary.loc[
    municipality_summary["kommun"].isin(selected_municipalities)
].copy()
selected_nodes = nodes.loc[nodes["kommun"].isin(selected_municipalities)]
selected_codes = {
    code
    for code, name in DALARNA_MUNICIPALITY_NAMES.items()
    if name in selected_municipalities
}

weights = selected_grid["befolkning_2025"].astype(float)
weighted_mean = float(np.average(selected_grid[grid_column], weights=weights))
expanded_values = np.repeat(
    selected_grid[grid_column].to_numpy(dtype=float),
    selected_grid["befolkning_2025"].to_numpy(dtype=int),
)
weighted_p90 = float(np.quantile(expanded_values, 0.9, method="inverted_cdf"))
population_over_threshold = int(
    selected_grid.loc[
        selected_grid[grid_column].gt(focus_threshold), "befolkning_2025"
    ].sum()
)
leader = selected_summary.sort_values(score_column, ascending=False).iloc[0]

with st.container(horizontal=True):
    st.metric(
        "Högst relativ signal",
        str(leader["kommun"]),
        help=(
            "Högst percentil bland visade kommuner. Percentilen är alltid "
            "beräknad mot samtliga 15 kommuner."
        ),
        border=True,
    )
    st.metric(
        f"Befolkningsvägt medel · {dimension.lower()}",
        f"{format_sv(weighted_mean, 1)} km",
        border=True,
    )
    st.metric(
        "90:e befolkningspercentilen",
        f"{format_sv(weighted_p90, 1)} km",
        help="90 procent av befolkningen i urvalet har högst detta fågelvägsavstånd.",
        border=True,
    )
    st.metric(
        f"Invånare över {format_sv(focus_threshold, 0)} km",
        format_sv(population_over_threshold),
        border=True,
    )

map_column, rank_column = st.columns([2.25, 1], gap="small")
with map_column:
    with st.container(border=True):
        st.subheader(metric_label)
        legend_labels = [
            f"Högst {format_sv(thresholds[0], 0)} km",
            f">{format_sv(thresholds[0], 0)}–{format_sv(thresholds[1], 0)} km",
            f">{format_sv(thresholds[1], 0)}–{format_sv(thresholds[2], 0)} km",
            f">{format_sv(thresholds[2], 0)}–{format_sv(thresholds[3], 0)} km",
            f">{format_sv(thresholds[3], 0)} km",
        ]
        with st.container(key="screening-map-canvas-v2"):
            render_map_legend(
                "Fågelvägsavstånd",
                [
                    (label, color, "square")
                    for label, color in zip(legend_labels, ACCESSIBILITY_HEX)
                ]
                + [
                    ("Servicenod", "#345C7D", "dot"),
                    ("Kommungräns", "#303942", "line"),
                ],
                "screening-map-canvas-v2",
            )
            st.pydeck_chart(
                make_screening_grid_map(
                    grid_geojson,
                    selected_grid,
                    selected_nodes,
                    selected_codes,
                    grid_column,
                    metric_label,
                    thresholds,
                ),
                height=610,
                key="screening-grid-map-v2",
            )
        st.caption(
            "Rutans mittpunkt används för avståndet. Beräkningen söker bland "
            "alla noder i Dalarna även om bara valda kommuners rutor visas."
        )

with rank_column:
    with st.container(border=True):
        st.subheader("Kommunjämförelse")
        ranked = selected_summary.sort_values(summary_column, ascending=False).rename(
            columns={
                "kommun": "Kommun",
                summary_column: "Befolkningsvägt avstånd (km)",
                score_column: "Percentil (0–100)",
            }
        )
        st.vega_lite_chart(
            ranked,
            {
                "mark": {"type": "bar", "cornerRadiusEnd": 2, "color": "#BE5B2F"},
                "encoding": {
                    "y": {
                        "field": "Kommun",
                        "type": "nominal",
                        "sort": "-x",
                        "title": None,
                    },
                    "x": {
                        "field": "Befolkningsvägt avstånd (km)",
                        "type": "quantitative",
                        "title": "Kilometer",
                    },
                    "tooltip": [
                        {"field": "Kommun", "type": "nominal"},
                        {
                            "field": "Befolkningsvägt avstånd (km)",
                            "type": "quantitative",
                            "format": ".1f",
                        },
                        {"field": "Percentil (0–100)", "type": "quantitative", "format": ".0f"},
                    ],
                },
            },
            height=500,
        )
        st.caption(
            f"Måttet beskriver {config['explanation']}. Högre värde innebär "
            "starkare signal för fortsatt granskning."
        )

st.subheader("Tre servicealternativ per kommun")
with st.container(border=True):
    distance_comparison = selected_summary[
        [
            "kommun",
            "befolkningsvagt_forsta_nod_km",
            "befolkningsvagt_andra_nod_km",
            "befolkningsvagt_alternativ_aktor_km",
        ]
    ].rename(
        columns={
            "kommun": "Kommun",
            "befolkningsvagt_forsta_nod_km": "Första nod",
            "befolkningsvagt_andra_nod_km": "Andra nod",
            "befolkningsvagt_alternativ_aktor_km": "Alternativ aktör",
        }
    ).melt(id_vars="Kommun", var_name="Alternativ", value_name="Avstånd (km)")
    st.bar_chart(
        distance_comparison,
        x="Kommun",
        y="Avstånd (km)",
        color="Alternativ",
        stack=False,
        height=390,
    )
    st.caption(
        "Staplarna är befolkningsviktade kommunmedel. De visar skillnaden mellan "
        "grundläggande tillgänglighet, nodredundans och aktörsalternativ."
    )

st.subheader("Kommununderlag")
screening_table = selected_summary[
    [
        "kommun",
        "befolkning_2025",
        "befolkade_rutor",
        "befolkningsvagt_forsta_nod_km",
        "p90_forsta_nod_km",
        "andel_over_10_km_forsta_nod",
        "befolkningsvagt_andra_nod_km",
        "befolkningsvagt_redundansgap_km",
        "andel_over_20_km_andra_nod",
        "befolkningsvagt_alternativ_aktor_km",
        "andel_over_20_km_alternativ_aktor",
        "andel_befolkning_narmast_enaktorsnod",
        "screening_forsta_nod",
        "screening_andra_nod",
        "screening_alternativ_aktor",
        "screening_redundansgap",
    ]
].rename(
    columns={
        "kommun": "Kommun",
        "befolkning_2025": "Befolkning 2025",
        "befolkade_rutor": "Befolkade rutor",
        "befolkningsvagt_forsta_nod_km": "Första nod (km)",
        "p90_forsta_nod_km": "P90 första nod (km)",
        "andel_over_10_km_forsta_nod": "Andel >10 km första",
        "befolkningsvagt_andra_nod_km": "Andra nod (km)",
        "befolkningsvagt_redundansgap_km": "Redundansgap (km)",
        "andel_over_20_km_andra_nod": "Andel >20 km andra",
        "befolkningsvagt_alternativ_aktor_km": "Alternativ aktör (km)",
        "andel_over_20_km_alternativ_aktor": "Andel >20 km alternativ aktör",
        "andel_befolkning_narmast_enaktorsnod": "Andel närmast enaktörsnod",
        "screening_forsta_nod": "Signal första nod",
        "screening_andra_nod": "Signal andra nod",
        "screening_alternativ_aktor": "Signal alternativ aktör",
        "screening_redundansgap": "Signal redundansgap",
    }
)
st.dataframe(
    screening_table.sort_values("Signal första nod", ascending=False),
    hide_index=True,
    column_config={
        "Kommun": st.column_config.TextColumn(pinned=True),
        "Befolkning 2025": st.column_config.NumberColumn(format="localized"),
        "Befolkade rutor": st.column_config.NumberColumn(format="localized"),
        **{
            column: st.column_config.NumberColumn(format="%.1f")
            for column in [
                "Första nod (km)",
                "P90 första nod (km)",
                "Andra nod (km)",
                "Redundansgap (km)",
                "Alternativ aktör (km)",
            ]
        },
        **{
            column: st.column_config.NumberColumn(format="percent")
            for column in [
                "Andel >10 km första",
                "Andel >20 km andra",
                "Andel >20 km alternativ aktör",
                "Andel närmast enaktörsnod",
            ]
        },
        **{
            column: st.column_config.ProgressColumn(min_value=0, max_value=100)
            for column in [
                "Signal första nod",
                "Signal andra nod",
                "Signal alternativ aktör",
                "Signal redundansgap",
            ]
        },
    },
)
st.download_button(
    ":material/download: Ladda ner kommununderlag",
    data=screening_table.to_csv(index=False).encode("utf-8-sig"),
    file_name="screening_tillganglighet_kommun.csv",
    mime="text/csv",
    type="tertiary",
)

st.subheader(f"Rutor med längst {dimension.lower()}")
longest = selected_grid.nlargest(30, grid_column)[
    [
        "rutid",
        "kommun",
        "befolkning_2025",
        "befolkning_65_plus_2025",
        "avstand_forsta_nod_km",
        "forsta_nod",
        "avstand_andra_nod_km",
        "andra_nod",
        "avstand_alternativ_aktor_km",
        "alternativ_aktor_nod",
        "nya_aktorer_vid_alternativ",
        "redundansgap_km",
    ]
].rename(
    columns={
        "rutid": "1 km-ruta",
        "kommun": "Kommun",
        "befolkning_2025": "Befolkning",
        "befolkning_65_plus_2025": "Befolkning 65+",
        "avstand_forsta_nod_km": "Första nod (km)",
        "forsta_nod": "Första nod",
        "avstand_andra_nod_km": "Andra nod (km)",
        "andra_nod": "Andra nod",
        "avstand_alternativ_aktor_km": "Alternativ aktör (km)",
        "alternativ_aktor_nod": "Nod med alternativ aktör",
        "nya_aktorer_vid_alternativ": "Nya aktörer",
        "redundansgap_km": "Redundansgap (km)",
    }
)
st.dataframe(
    longest,
    hide_index=True,
    column_config={
        "1 km-ruta": st.column_config.TextColumn(pinned=True),
        **{
            column: st.column_config.NumberColumn(format="%.1f")
            for column in [
                "Första nod (km)",
                "Andra nod (km)",
                "Alternativ aktör (km)",
                "Redundansgap (km)",
            ]
        },
    },
)

method = st.expander("Metod och begränsningar", on_change="rerun")
if method.open:
    with method:
        st.markdown(
            f"""
            - Varje befolkad 1 km-rutas mittpunkt jämförs med samtliga 236
              observerade fysiska noder i Dalarna. Kommunfiltret ändrar bara vad
              som visas och summeras.
            - **Första nod** är den närmaste fysiska noden. **Andra nod** är den
              näst närmaste separata fysiska noden.
            - **Alternativ aktör** är närmaste annan nod som erbjuder minst en
              aktör som saknas vid första noden. Måttet garanterar inte samma
              servicetyp, kapacitet, öppettid eller leveransfrekvens.
            - Kommunvärdena är medelavstånd viktade med rutbefolkning 2025.
              Percentilerna beräknas mot alla 15 kommuner och visas separat; de
              får inte summeras till ett riskindex.
            - Avstånden är fågelvägsavstånd i SWEREF 99 TM, inte vägnätsbaserad
              restid. Rutans mittpunkt och kommunanknytning förenklar verkligheten.
            - Servicenätet avser 2026 medan befolkningen avser 2025.

            **Rutkälla:** {grid_metadata['source']} · lager
            `{grid_metadata['layer']}` · hämtad {grid_metadata['retrieved_at_utc']}.
            """
        )
