"""Hypotetisk bortfallssimulering med 1 km-rutor och DeSO."""

import numpy as np
import pandas as pd
import streamlit as st

from dashboard_data import (
    aggregate_grid_accessibility_to_deso,
    calculate_grid_accessibility,
)
from dashboard_ui import (
    ACCESSIBILITY_HEX,
    DALARNA_MUNICIPALITY_NAMES,
    accessibility_band_labels,
    format_sv,
    load_deso_bundle,
    load_phase1_bundle,
    load_population_grid_bundle,
    make_simulation_map,
    render_map_legend,
)


@st.cache_data(show_spinner=False, max_entries=32)
def run_accessibility_scenario(
    grid: pd.DataFrame,
    node_data: pd.DataFrame,
    removed_node_ids: tuple[int, ...] = (),
    thresholds_km: tuple[float, float, float, float] = (5, 10, 20, 30),
) -> pd.DataFrame:
    return calculate_grid_accessibility(
        grid, node_data, removed_node_ids=removed_node_ids,
        thresholds_km=thresholds_km,
    )


(
    packages, service, nodes, profile, clusters, changes, actors, cases, data_directory
) = load_phase1_bundle()
grid_geojson, population_grid, grid_metadata = load_population_grid_bundle()
deso_geojson, deso_population, _, deso_metadata = load_deso_bundle()

st.caption(
    "Hypotetisk screening med servicenät 2026, SCB:s befolkning på 1 × 1 km-rutor "
    "2025 och DeSO 2025. Avstånden är fågelvägsavstånd, inte restid."
)

controls_column, map_column, chart_column = st.columns(
    [1.25, 3.25, 1.35], gap="small", vertical_alignment="top"
)
with controls_column:
    municipality_options = ["Hela Dalarna", *sorted(nodes["kommun"].dropna().unique())]
    selected_municipality = st.selectbox(
        "Geografiskt urval", municipality_options,
        key="simulation-municipality", persist_state="session",
    )

if selected_municipality == "Hela Dalarna":
    candidate_nodes = nodes
    selected_codes = None
    selected_grid = population_grid
    scope_label = "Dalarna"
else:
    candidate_nodes = nodes.loc[nodes["kommun"].eq(selected_municipality)]
    selected_codes = {
        code for code, name in DALARNA_MUNICIPALITY_NAMES.items()
        if name == selected_municipality
    }
    selected_grid = population_grid.loc[population_grid["kommunkod"].isin(selected_codes)]
    scope_label = f"{selected_municipality} kommun"

baseline_accessibility = run_accessibility_scenario(population_grid, nodes)
baseline_population = (
    baseline_accessibility.groupby("narmaste_nod_fore_id")["befolkning_2025"].sum().to_dict()
)
candidate_ids = sorted(
    candidate_nodes["kluster_id"].astype(int).tolist(),
    key=lambda node_id: (-baseline_population.get(node_id, 0), node_id),
)
node_lookup = nodes.set_index("kluster_id")
st.session_state.setdefault("simulation-removed-nodes", ())
active_ids = tuple(
    int(node_id) for node_id in st.session_state["simulation-removed-nodes"]
    if int(node_id) in candidate_ids
)
if active_ids != tuple(st.session_state["simulation-removed-nodes"]):
    st.session_state["simulation-removed-nodes"] = active_ids

removed_node_ids = active_ids
metric_options = {
    "Rutbefolkning 2025": "rutbefolkning_2025",
    "Absolut skillnad mot DeSO-befolkning": "absolut_befolkningsdifferens_pct",
}
if removed_node_ids:
    metric_options = {
        "Andel berörd befolkning": "andel_berord_befolkning",
        "Berörd befolkning": "berord_befolkning",
        "Berörda 65+": "berord_befolkning_65_plus",
        "Befolkningsvägd avståndsökning": "befolkningsvagd_avstandsokning_km",
        "Största avståndsökning": "storsta_avstandsokning_km",
        "Andel i sämre avståndsklass": "andel_samre_avstandsklass",
        "Andel över högsta gränsen": "andel_over_hogsta_grans",
        **metric_options,
    }

with controls_column:
    with st.container(border=True):
        st.markdown("**Kartval**")
        map_mode = st.segmented_control(
            "Analysenhet", ["1 km-rutor", "DeSO", "Båda"],
            default="1 km-rutor", key="simulation-map-mode",
        ) or "1 km-rutor"
        metric_label = next(iter(metric_options))
        if map_mode in {"DeSO", "Båda"}:
            metric_label = st.selectbox(
                "Mått för DeSO", list(metric_options),
                key="simulation-deso-metric",
            )
        quality_threshold = st.number_input(
            "Jämförelsegräns (%)", min_value=0.0, max_value=100.0,
            value=5.0, step=1.0, key="simulation-deso-quality-threshold",
            help="Markerar DeSO där rutbefolkning 2025 och publicerad "
            "DeSO-befolkning 2024 skiljer sig mer än gränsen.",
        )
        if map_mode == "Båda":
            grid_opacity = st.slider(
                "Rutornas täckning", 40, 220, 145,
                key="simulation-grid-opacity",
            )
            deso_opacity = st.slider(
                "DeSO:s täckning", 20, 200, 80,
                key="simulation-deso-opacity",
            )
        else:
            grid_opacity, deso_opacity = 175, 155

    with st.container(border=True):
        st.markdown("**Scenarioinställningar**")
        st.caption(
            "Kryssa i en eller flera noder. Kartan uppdateras först när du "
            "startar simuleringen."
        )
        node_choices = candidate_nodes.copy()
        node_choices["Nod"] = (
            node_choices["nodnamn"].astype(str) + " – "
            + node_choices["postort"].astype(str)
        )
        node_choices["Närmaste befolkning"] = (
            node_choices["kluster_id"].map(baseline_population).fillna(0).astype(int)
        )
        node_choices = node_choices.sort_values(
            ["Närmaste befolkning", "Nod"], ascending=[False, True]
        ).reset_index(drop=True)
        node_choices.insert(
            0, "Ta bort", node_choices["kluster_id"].isin(removed_node_ids)
        )
        editor_key = f"simulation-node-editor-{selected_municipality}"

        def apply_scenario() -> None:
            selected = node_choices["Ta bort"].astype(bool).copy()
            editor_state = st.session_state.get(editor_key, {})
            for row_index, changes in editor_state.get("edited_rows", {}).items():
                if "Ta bort" in changes:
                    selected.iloc[int(row_index)] = bool(changes["Ta bort"])
            st.session_state["simulation-removed-nodes"] = tuple(
                sorted(node_choices.loc[selected, "kluster_id"].astype(int))
            )

        with st.form(
            f"simulation-scenario-form-{selected_municipality}", border=False
        ):
            st.data_editor(
                node_choices[["Ta bort", "Nod", "Närmaste befolkning"]],
                hide_index=True, height=310, key=editor_key,
                disabled=["Nod", "Närmaste befolkning"],
                column_config={
                    "Ta bort": st.column_config.CheckboxColumn(
                        "Ta bort", help="Markera alla noder som ska ingå i bortfallet."
                    ),
                    "Nod": st.column_config.TextColumn(pinned=True),
                    "Närmaste befolkning": st.column_config.NumberColumn(
                        "Invånare närmast", format="localized"
                    ),
                },
            )
            with st.expander("Avancerade inställningar"):
                st.caption(
                    "Avståndsgränserna används för kartans fem färgklasser. "
                    "Standardvärdena fungerar för normal screening."
                )
                threshold_values = []
                for label, default, index in zip(
                    ["Grön till", "Gul till", "Orange till", "Röd till"],
                    [5.0, 10.0, 20.0, 30.0], range(4)
                ):
                    threshold_values.append(st.number_input(
                        f"{label} (km)", min_value=0.5, max_value=100.0,
                        value=default, step=0.5,
                        key=f"simulation-threshold-{index}",
                    ))
            thresholds = tuple(float(value) for value in threshold_values)
            valid_thresholds = all(
                a < b for a, b in zip(thresholds, thresholds[1:])
            )
            st.form_submit_button(
                "Simulera markerade bortfall", type="primary",
                icon=":material/play_arrow:", width="stretch",
                on_click=apply_scenario,
            )
        if not valid_thresholds:
            st.error("Avståndsgränserna måste vara strikt stigande.")

        def reset_simulation() -> None:
            st.session_state["simulation-removed-nodes"] = ()
            st.session_state.pop(editor_key, None)

        st.button(
            "Återställ scenario", icon=":material/restart_alt:",
            width="stretch", disabled=not removed_node_ids,
            on_click=reset_simulation,
        )

with map_column:
    map_slot = st.container()
with chart_column:
    chart_slot = st.container()

st.caption(
    "Kartan är huvudvyn. Kartvalen finns till vänster och diagrammet sammanfattar "
    "samma geografiska urval till höger."
)

removed_node_ids = tuple(st.session_state["simulation-removed-nodes"])

accessibility_all = run_accessibility_scenario(
    population_grid, nodes, removed_node_ids=removed_node_ids,
    thresholds_km=thresholds,
)
deso_summary_all = aggregate_grid_accessibility_to_deso(
    accessibility_all, deso_population, quality_threshold_pct=quality_threshold
)

selected_ids = set(selected_grid["rutid"])
accessibility = accessibility_all.loc[accessibility_all["rutid"].isin(selected_ids)].copy()
deso_summary = deso_summary_all if selected_codes is None else deso_summary_all.loc[
    deso_summary_all["desokod"].str[:4].isin(selected_codes)
].copy()
band_labels = accessibility_band_labels(thresholds)
accessibility["Avståndsklass före"] = accessibility["klass_fore"].map(dict(enumerate(band_labels)))
accessibility["Avståndsklass efter"] = accessibility["klass_efter"].map(dict(enumerate(band_labels)))

deso_metric = metric_options[metric_label]

affected = accessibility.loc[accessibility["paverkad"]]
affected_population = int(affected["befolkning_2025"].sum())
affected_older = int(affected["befolkning_65_plus_2025"].sum())
worse_population = int(accessibility.loc[
    accessibility["samre_avstandsklass"], "befolkning_2025"
].sum())
weighted_increase = float(np.average(
    affected["avstandsokning_km"], weights=affected["befolkning_2025"]
)) if affected_population else 0.0
maximum_increase = float(affected["avstandsokning_km"].max()) if affected_population else 0.0
affected_deso = int(deso_summary["berort_deso"].sum())

if not removed_node_ids:
    st.info(
        "Nuläget visas direkt. Rutorna är tända som standard; välj DeSO eller Båda "
        "för en aggregerad vy. Starta simuleringen när du vill pröva ett bortfall.",
        icon=":material/info:",
    )
else:
    removed_names = node_lookup.loc[list(removed_node_ids), "nodnamn"].astype(str).tolist()
    removed_summary = ", ".join(removed_names[:3])
    if len(removed_names) > 3:
        removed_summary += f" och {len(removed_names) - 3} till"
    st.warning(
        f"Aktivt scenario: **{format_sv(len(removed_node_ids))} noder** tas "
        f"hypotetiskt bort: {removed_summary}. "
        "Källdatan är oförändrad.", icon=":material/science:",
    )
    with st.container(horizontal=True):
        st.metric("Befolkning vars närmaste nod ändras", format_sv(affected_population), border=True)
        st.metric("Varav 65+", format_sv(affected_older), border=True)
        st.metric("Berörda DeSO", format_sv(affected_deso), border=True)
        st.metric("Flyttas till sämre klass", format_sv(worse_population), border=True)
        st.metric("Befolkningsvägd ökning", f"{format_sv(weighted_increase, 1)} km", border=True)
        st.metric("Största ökning", f"{format_sv(maximum_increase, 1)} km", border=True)

with map_slot.container():
    with st.container(border=True, horizontal_alignment="center"):
        title = "Tillgänglighet efter bortfall" if removed_node_ids else "Tillgänglighet i nuläget"
        st.subheader(f"{title} – {scope_label}")
        legend_items = []
        if map_mode in {"1 km-rutor", "Båda"}:
            legend_items += [(label, color, "square") for label, color in zip(band_labels, ACCESSIBILITY_HEX)]
        if map_mode in {"DeSO", "Båda"}:
            legend_items += [
                (f"Lågt {metric_label.lower()}", "#D9C7E2", "square"),
                (f"Högt {metric_label.lower()}", "#4F285E", "square"),
            ]
        if removed_node_ids and map_mode in {"1 km-rutor", "Båda"}:
            legend_items.append(("Påverkad rutas mörka kontur", "#2B3138", "line"))
        legend_items += [("Kvarvarande nod", "#345C7D", "dot")]
        if removed_node_ids:
            legend_items.append(("Simulerade bortfall", "#691C2D", "cross"))
        legend_items.append(("Kommungräns", "#303942", "line"))
        with st.container(key="simulation-impact-map-canvas"):
            render_map_legend(
                "Kartförklaring", legend_items, "simulation-impact-map-canvas"
            )
            st.pydeck_chart(make_simulation_map(
                grid_geojson, accessibility, nodes, removed_node_ids, selected_codes,
                map_mode=map_mode, deso_geojson=deso_geojson,
                deso_summary=deso_summary, deso_metric=deso_metric,
                deso_metric_label=metric_label, grid_opacity=grid_opacity,
                deso_opacity=deso_opacity,
            ), height=720, key="simulation-impact-map")
        st.caption(
            "Rutans mittpunkt används för avstånd och DeSO-/kommunanknytning. "
            "DeSO-värdena är summeringar av exakt samma 1 km-rutor."
        )

with chart_slot.container():
    with st.container(border=True):
        st.subheader("Befolkning per avståndsklass")
        frames = []
        scenarios = [("Nuläge", "Avståndsklass före")]
        if removed_node_ids:
            scenarios.append(("Efter", "Avståndsklass efter"))
        for scenario, column in scenarios:
            frame = (accessibility.groupby(column, observed=False)["befolkning_2025"]
                     .sum().reindex(band_labels, fill_value=0).rename("Befolkning")
                     .reset_index().rename(columns={column: "Avståndsklass"}))
            frame["Scenario"] = scenario
            frames.append(frame)
        band_summary = pd.concat(frames, ignore_index=True)
        st.vega_lite_chart(band_summary, {
            "mark": {"type": "bar", "cornerRadiusEnd": 2},
            "encoding": {
                "y": {"field": "Avståndsklass", "type": "nominal", "sort": band_labels, "title": None},
                "yOffset": {"field": "Scenario", "type": "nominal", "sort": ["Nuläge", "Efter"]},
                "x": {"field": "Befolkning", "type": "quantitative", "title": "Befolkning 2025"},
                "color": {"field": "Avståndsklass", "type": "nominal", "scale": {"domain": band_labels, "range": ACCESSIBILITY_HEX}, "legend": None},
                "opacity": {"field": "Scenario", "type": "nominal", "scale": {"domain": ["Nuläge", "Efter"], "range": [0.5, 1.0]}, "legend": {"title": None, "orient": "bottom"}},
                "tooltip": [{"field": "Scenario"}, {"field": "Avståndsklass"}, {"field": "Befolkning", "type": "quantitative"}],
            },
        }, height=390)
        if not removed_node_ids:
            st.markdown(
                f"**Nuläge:** Diagrammet fördelar {format_sv(accessibility['befolkning_2025'].sum())} "
                f"invånare i {scope_label} efter avståndet till närmaste servicenod."
            )
        elif affected_population:
            st.markdown(
                f"**Scenarioeffekt:** {format_sv(affected_population)} invånare får en annan "
                f"närmaste nod och {format_sv(worse_population)} hamnar i en sämre klass. "
                f"Det berör {format_sv(affected_deso)} DeSO; den befolkningsvägda ökningen "
                f"är {format_sv(weighted_increase, 1)} km och den största {format_sv(maximum_increase, 1)} km."
            )
        else:
            st.markdown("**Scenarioeffekt:** Ingen redovisad invånare i urvalet får en annan närmaste nod.")

if removed_node_ids and map_mode in {"DeSO", "Båda"}:
    st.subheader("Mest berörda DeSO")
    deso_table = deso_summary.loc[deso_summary["berort_deso"]].nlargest(30, "berord_befolkning")[
        ["desokod", "kommun", "rutbefolkning_2025", "berord_befolkning",
         "berord_befolkning_65_plus", "berorda_rutor", "andel_berord_befolkning",
         "befolkningsvagd_avstandsokning_km", "storsta_avstandsokning_km",
         "vanligaste_alternativa_nod"]
    ].rename(columns={
        "desokod": "DeSO", "kommun": "Kommun", "rutbefolkning_2025": "Rutbefolkning 2025",
        "berord_befolkning": "Berörda", "berord_befolkning_65_plus": "Berörda 65+",
        "berorda_rutor": "Berörda rutor", "andel_berord_befolkning": "Andel berörda",
        "befolkningsvagd_avstandsokning_km": "Vägd ökning (km)",
        "storsta_avstandsokning_km": "Största ökning (km)",
        "vanligaste_alternativa_nod": "Vanligaste alternativa nod",
    })
    st.dataframe(deso_table, hide_index=True, column_config={
        "DeSO": st.column_config.TextColumn(pinned=True),
        "Andel berörda": st.column_config.NumberColumn(format="percent"),
        "Vägd ökning (km)": st.column_config.NumberColumn(format="%.1f"),
        "Största ökning (km)": st.column_config.NumberColumn(format="%.1f"),
    })

if removed_node_ids and map_mode in {"1 km-rutor", "Båda"}:
    st.subheader("Mest påverkade befolkade rutor")
    affected_table = affected.nlargest(30, "avstandsokning_km")[[
        "rutid", "desokod", "kommun", "befolkning_2025", "befolkning_65_plus_2025",
        "avstand_fore_km", "avstand_efter_km", "avstandsokning_km",
        "narmaste_nod_efter", "samre_avstandsklass",
    ]].rename(columns={
        "rutid": "1 km-ruta", "desokod": "DeSO", "kommun": "Kommun",
        "befolkning_2025": "Befolkning 2025", "befolkning_65_plus_2025": "Befolkning 65+",
        "avstand_fore_km": "Avstånd före (km)", "avstand_efter_km": "Avstånd efter (km)",
        "avstandsokning_km": "Ökning (km)", "narmaste_nod_efter": "Närmaste kvarvarande nod",
        "samre_avstandsklass": "Sämre klass",
    })
    st.dataframe(affected_table, hide_index=True, column_config={
        "1 km-ruta": st.column_config.TextColumn(pinned=True),
        "Avstånd före (km)": st.column_config.NumberColumn(format="%.1f"),
        "Avstånd efter (km)": st.column_config.NumberColumn(format="%.1f"),
        "Ökning (km)": st.column_config.NumberColumn(format="%.1f"),
        "Sämre klass": st.column_config.CheckboxColumn(),
    })

if map_mode in {"DeSO", "Båda"}:
    comparison = st.expander("Jämförelse: aggregerad 1 km-ruta och publicerad DeSO-befolkning")
    with comparison:
        flagged = int(deso_summary["kvalitetsflagga"].sum())
        st.caption(
            f"{flagged} av {len(deso_summary)} DeSO avviker mer än {format_sv(quality_threshold, 1)} %. "
            "Jämförelsen gäller olika referensår (ruta 2025, DeSO 2024) och är en kvalitetsindikator, inte ett felmått."
        )
        comparison_table = deso_summary.nlargest(30, "absolut_befolkningsdifferens_pct")[[
            "desokod", "kommun", "rutbefolkning_2025", "deso_befolkning_2024",
            "befolkningsdifferens", "befolkningsdifferens_pct", "befolkade_rutor", "kvalitetsflagga",
        ]].rename(columns={
            "desokod": "DeSO", "kommun": "Kommun", "rutbefolkning_2025": "Rutbefolkning 2025",
            "deso_befolkning_2024": "DeSO-befolkning 2024", "befolkningsdifferens": "Skillnad antal",
            "befolkningsdifferens_pct": "Skillnad (%)", "befolkade_rutor": "Befolkade rutor",
            "kvalitetsflagga": "Över vald gräns",
        })
        st.dataframe(comparison_table, hide_index=True, column_config={
            "DeSO": st.column_config.TextColumn(pinned=True),
            "Skillnad (%)": st.column_config.NumberColumn(format="%.1f %%"),
            "Över vald gräns": st.column_config.CheckboxColumn(),
        })

with st.expander("Metod och avgränsningar"):
    st.markdown(f"""
    - 1 km-rutorna är beräkningsbas i alla tre kartlägen. DeSO summerar samma rader, så befolkningen dubbelräknas inte.
    - Scenariot tar bort de markerade noderna ur beräkningen, aldrig ur källdatan. Alla kvarvarande noder i Dalarna kan bli närmast.
    - Fågelvägsavstånd i SWEREF 99 TM är ett screeningmått och ersätter inte vägnätsbaserad restid, öppettider eller kapacitet.
    - Kommun och DeSO tilldelas efter rutans mittpunkt. Gränsrutor kan därför innehålla befolkning på båda sidor om en gräns.
    - SCB använder statistiskt röjandeskydd. Ålderssummeringar kan avvika från totalbefolkningen.
    - Rutbefolkning 2025 och publicerad DeSO-befolkning 2024 visas separat eftersom de har olika referensår.

    **Rutkälla:** {grid_metadata['source']} · lager `{grid_metadata['layer']}` · hämtad {grid_metadata['retrieved_at_utc']}.
    """)
