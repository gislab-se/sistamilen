"""Delad dataladdning och visualisering för Streamlit-sidorna."""

import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from dashboard_data import build_service_nodes, load_dashboard_data


PROJECT_ROOT = Path(__file__).resolve().parent
WORKING_DIR = PROJECT_ROOT / "data" / "working"
DERIVED_DIR = PROJECT_ROOT / "data" / "derived"
EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"

DALARNA_MUNICIPALITY_NAMES = {
    "2021": "Vansbro",
    "2023": "Malung-Sälen",
    "2026": "Gagnef",
    "2029": "Leksand",
    "2031": "Rättvik",
    "2034": "Orsa",
    "2039": "Älvdalen",
    "2061": "Smedjebacken",
    "2062": "Mora",
    "2080": "Falun",
    "2081": "Borlänge",
    "2082": "Säter",
    "2083": "Hedemora",
    "2084": "Avesta",
    "2085": "Ludvika",
}

# Gemensam visuell semantik i diagram och kartor.
NODE_TOTAL_COLOR = "#5F6873"
ACTOR_SERVICE_COLOR = "#406F98"
SERVICE_TYPE_COLOR = "#76558F"
MAP_SINGLE_ACTOR_COLOR = [190, 91, 47, 205]
MAP_MULTI_ACTOR_COLOR = [24, 119, 109, 205]
MUNICIPAL_BOUNDARY_COLOR = [48, 57, 66, 225]
ACCESSIBILITY_COLORS = [
    [31, 137, 91, 175],
    [238, 196, 67, 180],
    [226, 126, 43, 185],
    [198, 55, 52, 190],
    [105, 28, 45, 200],
]
ACCESSIBILITY_HEX = ["#1F895B", "#EEC443", "#E27E2B", "#C63734", "#691C2D"]


@st.cache_data(show_spinner="Läser och förbereder Fas 1-data …")
def load_phase1_bundle() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    str,
]:
    """Läs statiska källor och arbetsregister en gång per appsession."""
    packages, service, profile, clusters, data_dir = load_dashboard_data(PROJECT_ROOT)
    nodes = build_service_nodes(service, clusters)
    changes = pd.read_csv(
        WORKING_DIR / "forandringsregister.csv", encoding="utf-8-sig"
    )
    actors = pd.read_csv(WORKING_DIR / "aktorsmatris.csv", encoding="utf-8-sig")
    cases = pd.read_csv(WORKING_DIR / "platsfall.csv", encoding="utf-8-sig")
    return (
        packages,
        service,
        nodes,
        profile,
        clusters,
        changes,
        actors,
        cases,
        str(data_dir),
    )


@st.cache_data(show_spinner=False)
def load_phase1_status_bundle() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Läs Fas 1-status och RUS-koppling från gemensamma arbetsregister."""
    status = pd.read_csv(WORKING_DIR / "fas1_status.csv", encoding="utf-8-sig")
    rus = pd.read_csv(WORKING_DIR / "rus_koppling.csv", encoding="utf-8-sig")
    return status, rus


@st.cache_data(show_spinner="Läser SCB:s DeSO-underlag …")
def load_deso_bundle() -> tuple[dict, pd.DataFrame, pd.DataFrame, dict]:
    """Läs det lokalt sparade, reproducerbara DeSO-uttaget från SCB."""
    geojson_path = DERIVED_DIR / "deso_2025_dalarna.geojson"
    population_path = DERIVED_DIR / "deso_befolkning_2024.csv"
    node_crosswalk_path = DERIVED_DIR / "nod_deso_2025.csv"
    metadata_path = EXTERNAL_DIR / "scb" / "source_metadata.json"
    required = [
        geojson_path,
        population_path,
        node_crosswalk_path,
        metadata_path,
    ]
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "DeSO-underlaget saknas. Kör scripts/fetch_scb_deso.py. Saknas: "
            + ", ".join(missing)
        )
    with geojson_path.open(encoding="utf-8") as file:
        geojson = json.load(file)
    population = pd.read_csv(population_path, encoding="utf-8-sig")
    node_crosswalk = pd.read_csv(node_crosswalk_path, encoding="utf-8-sig")
    with metadata_path.open(encoding="utf-8") as file:
        metadata = json.load(file)
    population["kommunkod"] = population["desokod"].str[:4]
    population["kommun"] = population["kommunkod"].map(DALARNA_MUNICIPALITY_NAMES)
    return geojson, population, node_crosswalk, metadata


@st.cache_data(show_spinner="Läser SCB:s 1 km-rutor …")
def load_population_grid_bundle() -> tuple[dict, pd.DataFrame, dict]:
    """Läs lokalt, reproducerbart uttag av SCB:s rutbefolkning 2025."""
    geojson_path = DERIVED_DIR / "befolkning_1km_2025_dalarna.geojson"
    table_path = DERIVED_DIR / "befolkning_1km_2025_dalarna.csv"
    metadata_path = EXTERNAL_DIR / "scb" / "population_grid_source_metadata.json"
    required = [geojson_path, table_path, metadata_path]
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Rutbefolkningen saknas. Kör scripts/fetch_scb_population_grid.py. "
            "Saknas: "
            + ", ".join(missing)
        )
    with geojson_path.open(encoding="utf-8") as file:
        geojson = json.load(file)
    grid = pd.read_csv(
        table_path,
        encoding="utf-8-sig",
        dtype={"rutid": str, "kommunkod": str},
    )
    grid["kommun"] = grid["kommunkod"].map(DALARNA_MUNICIPALITY_NAMES)
    with metadata_path.open(encoding="utf-8") as file:
        metadata = json.load(file)
    return geojson, grid, metadata


def build_municipality_boundaries(geojson: dict) -> dict:
    """Lös fram kommunperimetrar genom att ta bort interna DeSO-kanter."""
    edge_counts: dict[
        tuple[tuple[float, float], tuple[float, float]], dict[str, int]
    ] = {}

    for feature in geojson["features"]:
        municipality_code = str(feature["properties"]["kommunkod"])
        geometry = feature["geometry"]
        polygons = (
            [geometry["coordinates"]]
            if geometry["type"] == "Polygon"
            else geometry["coordinates"]
        )
        for polygon in polygons:
            for ring in polygon:
                for start, end in zip(ring, ring[1:]):
                    start_point = (float(start[0]), float(start[1]))
                    end_point = (float(end[0]), float(end[1]))
                    edge = tuple(sorted((start_point, end_point)))
                    counts = edge_counts.setdefault(edge, {})
                    counts[municipality_code] = counts.get(municipality_code, 0) + 1

    boundary_groups: dict[tuple[str, ...], list[list[list[float]]]] = {}
    for (start, end), counts in edge_counts.items():
        municipality_codes = tuple(
            sorted(code for code, count in counts.items() if count == 1)
        )
        if municipality_codes:
            boundary_groups.setdefault(municipality_codes, []).append(
                [[start[0], start[1]], [end[0], end[1]]]
            )

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "kommunkoder": list(codes),
                    "kommuner": [
                        DALARNA_MUNICIPALITY_NAMES.get(code, code) for code in codes
                    ],
                },
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": lines,
                },
            }
            for codes, lines in boundary_groups.items()
            if lines
        ],
    }


@st.cache_data(show_spinner=False)
def load_municipality_boundaries() -> dict:
    """Skapa kommungränser från det lokala DeSO 2025-uttaget."""
    geojson_path = DERIVED_DIR / "deso_2025_dalarna.geojson"
    if not geojson_path.exists():
        raise FileNotFoundError(
            "DeSO-underlaget saknas. Kör scripts/fetch_scb_deso.py."
        )
    with geojson_path.open(encoding="utf-8") as file:
        return build_municipality_boundaries(json.load(file))


def _municipality_boundary_layer(
    municipality_codes: set[str] | None = None,
) -> pdk.Layer:
    boundaries = load_municipality_boundaries()
    if municipality_codes:
        boundaries = {
            "type": "FeatureCollection",
            "features": [
                feature
                for feature in boundaries["features"]
                if municipality_codes.intersection(
                    map(str, feature["properties"]["kommunkoder"])
                )
            ],
        }
    return pdk.Layer(
        "GeoJsonLayer",
        id="kommungranser-deso-2025",
        data=boundaries,
        get_line_color=MUNICIPAL_BOUNDARY_COLOR,
        line_width_min_pixels=1.6,
        stroked=True,
        filled=False,
        pickable=False,
    )


@st.cache_data(show_spinner="Läser SCB:s platsområden …")
def load_place_area_bundle() -> tuple[dict, dict]:
    """Läs lokala SCB-uttag för tätort, småort och fritidshusområde."""
    geojson_path = DERIVED_DIR / "scb_platsomraden_dalarna.geojson"
    metadata_path = EXTERNAL_DIR / "scb" / "place_areas_source_metadata.json"
    if not geojson_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            "SCB:s platsområden saknas. Kör scripts/fetch_scb_place_areas.py."
        )
    with geojson_path.open(encoding="utf-8") as file:
        geojson = json.load(file)
    with metadata_path.open(encoding="utf-8") as file:
        metadata = json.load(file)
    return geojson, metadata


def format_sv(value: float, decimals: int = 0) -> str:
    """Formatera tal med svenskt decimaltecken och fast mellanslag."""
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def accessibility_band_labels(
    thresholds_km: tuple[float, float, float, float],
) -> list[str]:
    first, second, third, fourth = thresholds_km
    return [
        f"Högst {format_sv(first, 0)} km",
        f">{format_sv(first, 0)}–{format_sv(second, 0)} km",
        f">{format_sv(second, 0)}–{format_sv(third, 0)} km",
        f">{format_sv(third, 0)}–{format_sv(fourth, 0)} km",
        f">{format_sv(fourth, 0)} km",
    ]


def render_map_legend(
    title: str,
    items: list[tuple[str, str, str]],
    canvas_key: str,
) -> None:
    """Rita en fast, tillgänglig legend ovanpå en nycklad kartcontainer."""
    legend_id = f"legend-{canvas_key}"
    item_markup = []
    for label, color, shape in items:
        safe_label = html.escape(label)
        safe_color = html.escape(color)
        symbol_class = f"map-legend-symbol map-legend-{shape}"
        item_markup.append(
            f'<div class="map-legend-item"><span class="{symbol_class}" '
            f'style="--legend-color:{safe_color}"></span><span>{safe_label}</span></div>'
        )
    st.html(
        f"""
        <style>
        .st-key-{canvas_key} {{ position: relative; }}
        .st-key-{canvas_key} div[data-testid="stElementContainer"]:has(#{legend_id}) {{
            position: absolute; top: 12px; left: 12px; z-index: 20; width: auto;
        }}
        #{legend_id} {{
            background: rgba(255,255,255,.94); border: 1px solid rgba(49,57,66,.22);
            border-radius: 8px; box-shadow: 0 2px 8px rgba(26,32,39,.16);
            color: #29313a; font: 12px/1.35 sans-serif; padding: 9px 11px;
            max-width: 245px;
        }}
        #{legend_id} .map-legend-title {{ font-weight: 650; margin-bottom: 5px; }}
        #{legend_id} .map-legend-item {{
            display: flex; align-items: center; gap: 7px; margin: 3px 0;
        }}
        #{legend_id} .map-legend-symbol {{
            background: var(--legend-color); display: inline-block; flex: 0 0 auto;
        }}
        #{legend_id} .map-legend-dot {{
            width: 10px; height: 10px; border-radius: 50%; border: 1px solid white;
            box-shadow: 0 0 0 1px rgba(40,45,50,.35);
        }}
        #{legend_id} .map-legend-square {{ width: 13px; height: 13px; opacity: .9; }}
        #{legend_id} .map-legend-gradient {{ width: 28px; height: 12px; opacity: .9; }}
        #{legend_id} .map-legend-line {{ width: 17px; height: 3px; border-radius: 2px; }}
        #{legend_id} .map-legend-cross {{
            width: 12px; height: 12px; border: 3px solid var(--legend-color);
            background: white; transform: rotate(45deg); border-radius: 2px;
        }}
        </style>
        <div id="{legend_id}" role="group" aria-label="Kartlegend">
          <div class="map-legend-title">{html.escape(title)}</div>
          {''.join(item_markup)}
        </div>
        """
    )


def _map_view(frame: pd.DataFrame) -> pdk.ViewState:
    lon_span = frame["lon"].max() - frame["lon"].min()
    lat_span = frame["lat"].max() - frame["lat"].min()
    span = max(lon_span, lat_span)
    zoom = (
        6.0
        if span > 3
        else 7.0
        if span > 1.5
        else 8.0
        if span > 0.7
        else 9.0
        if span > 0.2
        else 11.0
    )
    return pdk.ViewState(
        latitude=float(frame["lat"].mean()),
        longitude=float(frame["lon"].mean()),
        zoom=zoom,
        pitch=0,
    )


def _geojson_view(geojson: dict) -> pdk.ViewState:
    pairs: list[tuple[float, float]] = []

    def collect(value: object) -> None:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            pairs.append((float(value[0]), float(value[1])))
        elif isinstance(value, list):
            for item in value:
                collect(item)

    for feature in geojson["features"]:
        collect(feature["geometry"]["coordinates"])
    if not pairs:
        return pdk.ViewState(latitude=61.0, longitude=14.5, zoom=6.3)
    return _map_view(pd.DataFrame(pairs, columns=["lon", "lat"]))


def make_node_map(
    nodes: pd.DataFrame,
    municipality_codes: set[str] | None = None,
) -> pdk.Deck:
    """Visa adress-/servicenoder; orange betyder endast en aktör i källan."""
    map_data = nodes.dropna(subset=["lon", "lat"]).copy()
    map_data["kartfarg"] = map_data["en_aktor"].map(
        {True: MAP_SINGLE_ACTOR_COLOR, False: MAP_MULTI_ACTOR_COLOR}
    )
    map_data["narmaste_text"] = map_data["narmaste_annan_nod_km"].map(
        lambda value: f"{value:.1f} km"
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        id="servicenoder",
        data=map_data,
        get_position="[lon, lat]",
        get_fill_color="kartfarg",
        get_line_color=[255, 255, 255, 220],
        get_radius=650,
        radius_min_pixels=5,
        radius_max_pixels=13,
        line_width_min_pixels=1,
        stroked=True,
        pickable=True,
    )
    boundaries = load_municipality_boundaries()
    if municipality_codes:
        boundaries = {
            "type": "FeatureCollection",
            "features": [
                feature
                for feature in boundaries["features"]
                if municipality_codes.intersection(
                    map(str, feature["properties"]["kommunkoder"])
                )
            ],
        }
    view_state = _geojson_view(boundaries) if municipality_codes else _map_view(map_data)
    return pdk.Deck(
        map_style=None,
        initial_view_state=view_state,
        layers=[_municipality_boundary_layer(municipality_codes), layer],
        tooltip={
            "text": "{nodnamn}\n{postort}, {kommun}\n{antal_aktorer} aktör(er): "
            "{aktorer}\n{servicetyper}\nNärmaste annan nod: {narmaste_text}"
        },
    )


def make_simulation_map(
    grid_geojson: dict,
    accessibility: pd.DataFrame,
    nodes: pd.DataFrame,
    removed_node_ids: int | tuple[int, ...] | list[int] | set[int] | None,
    municipality_codes: set[str] | None,
    map_mode: str = "1 km-rutor",
    deso_geojson: dict | None = None,
    deso_summary: pd.DataFrame | None = None,
    deso_metric: str = "rutbefolkning_2025",
    deso_metric_label: str = "Rutbefolkning 2025",
    grid_opacity: int = 175,
    deso_opacity: int = 155,
) -> pdk.Deck:
    """Visa tillgänglighet som 1 km-rutor, DeSO eller båda."""
    if map_mode not in {"1 km-rutor", "DeSO", "Båda"}:
        raise ValueError(f"Okänt kartläge: {map_mode}")
    if removed_node_ids is None:
        removed_ids: set[int] = set()
    elif isinstance(removed_node_ids, (int, np.integer)):
        removed_ids = {int(removed_node_ids)}
    else:
        removed_ids = {int(value) for value in removed_node_ids}
    lookup = accessibility.set_index("rutid").to_dict(orient="index")
    map_rows = []
    for feature in grid_geojson["features"]:
        grid_id = str(feature["properties"]["rutid"])
        values = lookup.get(grid_id)
        if values is None:
            continue
        class_index = int(values["klass_efter"])
        properties = dict(feature["properties"])
        properties.update(
            {
                "fill_color": [
                    *ACCESSIBILITY_COLORS[class_index][:3], int(grid_opacity)
                ],
                "line_color": [43, 49, 56, 210]
                if bool(values["paverkad"])
                else [255, 255, 255, 70],
                "avstand_fore": f"{values['avstand_fore_km']:.1f} km".replace(".", ","),
                "avstand_efter": f"{values['avstand_efter_km']:.1f} km".replace(".", ","),
                "avstandsokning": f"{values['avstandsokning_km']:.1f} km".replace(".", ","),
                "narmaste_efter": values["narmaste_nod_efter"],
                "kommun": values["kommun"],
                "befolkning_text": format_sv(values["befolkning_2025"]),
                "aldre_text": format_sv(values["befolkning_65_plus_2025"]),
                "paverkad_text": "Ja" if bool(values["paverkad"]) else "Nej",
                "samre_klass_text": "Ja"
                if bool(values["samre_avstandsklass"])
                else "Nej",
                "avstandsklass_efter": values.get(
                    "Avståndsklass efter", f"Klass {class_index + 1}"
                ),
                "tooltip_title": f"1 km-ruta {grid_id}",
                "tooltip_line_1": f"DeSO: {values.get('desokod', '–')}",
                "tooltip_line_2": f"Kommun: {values['kommun']}",
                "tooltip_line_3": f"Befolkning 2025: {format_sv(values['befolkning_2025'])}",
                "tooltip_line_4": f"Befolkning 65+: {format_sv(values['befolkning_65_plus_2025'])}",
                "tooltip_line_5": (
                    f"Avstånd före/efter: {values['avstand_fore_km']:.1f} / "
                    f"{values['avstand_efter_km']:.1f} km"
                ).replace(".", ","),
                "tooltip_line_6": (
                    f"Ökning: {values['avstandsokning_km']:.1f} km"
                ).replace(".", ","),
                "tooltip_line_7": f"Närmaste nod: {values['narmaste_nod_efter']}",
                "tooltip_line_8": "Närmaste nod ändras: " + (
                    "Ja" if bool(values["paverkad"]) else "Nej"
                ),
                "tooltip_line_9": "Sämre avståndsklass: " + (
                    "Ja" if bool(values["samre_avstandsklass"]) else "Nej"
                ),
                "tooltip_line_10": "",
            }
        )
        geometry = feature["geometry"]
        polygons = (
            [geometry["coordinates"]]
            if geometry["type"] == "Polygon"
            else geometry["coordinates"]
        )
        for polygon in polygons:
            map_rows.append({**properties, "polygon": polygon[0]})

    grid_layer = pdk.Layer(
        "PolygonLayer",
        id="befolkningstillganglighet-1km",
        data=map_rows,
        get_polygon="polygon",
        get_fill_color="fill_color",
        get_line_color="line_color",
        line_width_min_pixels=0.5,
        stroked=True,
        filled=True,
        pickable=True,
        auto_highlight=True,
    )
    layers: list[pdk.Layer] = []
    if map_mode in {"DeSO", "Båda"}:
        if deso_geojson is None or deso_summary is None:
            raise ValueError("DeSO-läget kräver geometri och summerade DeSO-data.")
        deso_lookup = deso_summary.set_index("desokod").to_dict(orient="index")
        positive = pd.to_numeric(
            deso_summary[deso_metric], errors="coerce"
        ).fillna(0)
        positive = positive.loc[positive.gt(0)]
        scale_max = float(positive.quantile(0.95)) if len(positive) else 1.0
        scale_max = max(scale_max, 1e-9)
        palette = [
            [242, 238, 245], [217, 199, 226], [177, 139, 196],
            [128, 85, 143], [79, 40, 94],
        ]
        deso_rows = []
        for feature in deso_geojson["features"]:
            code = str(feature["properties"].get("desokod", ""))
            values = deso_lookup.get(code)
            if values is None:
                continue
            metric_value = float(values.get(deso_metric, 0) or 0)
            color_index = min(4, int(max(metric_value, 0) / scale_max * 4))
            color = palette[color_index] if metric_value > 0 else [231, 234, 236]
            metric_text = (
                f"{metric_value * 100:.1f} %"
                if deso_metric.startswith("andel_")
                else f"{metric_value:.1f} %"
                if deso_metric.endswith("_pct")
                else f"{metric_value:.1f} km"
                if deso_metric.endswith("_km")
                else format_sv(metric_value)
            ).replace(".", ",")
            diff = float(values.get("befolkningsdifferens_pct", 0) or 0)
            row = {
                "fill_color": [*color, int(deso_opacity)],
                "line_color": [79, 40, 94, 225],
                "tooltip_title": f"DeSO {code}",
                "tooltip_line_1": f"Kommun: {values.get('kommun', '–')}",
                "tooltip_line_2": f"{deso_metric_label}: {metric_text}",
                "tooltip_line_3": (
                    ""
                    if deso_metric == "rutbefolkning_2025"
                    else f"Rutbefolkning 2025: {format_sv(values.get('rutbefolkning_2025', 0))}"
                ),
                "tooltip_line_4": f"DeSO-befolkning 2024: {format_sv(values.get('deso_befolkning_2024', 0))}",
                "tooltip_line_5": f"Skillnad mellan underlagen: {diff:+.1f} %".replace(".", ","),
                "tooltip_line_6": (
                    f"Berörd befolkning: {format_sv(values.get('berord_befolkning', 0))} "
                    f"({float(values.get('andel_berord_befolkning', 0)) * 100:.1f} %)"
                ).replace(".", ","),
                "tooltip_line_7": (
                    f"Berörda 65+: {format_sv(values.get('berord_befolkning_65_plus', 0))}; "
                    f"rutor: {format_sv(values.get('berorda_rutor', 0))}"
                ),
                "tooltip_line_8": (
                    "Vägd/max ökning: "
                    f"{float(values.get('befolkningsvagd_avstandsokning_km', 0)):.1f} / "
                    f"{float(values.get('storsta_avstandsokning_km', 0)):.1f} km"
                ).replace(".", ","),
                "tooltip_line_9": "Vanligaste alternativa nod: "
                f"{values.get('vanligaste_alternativa_nod', 'Ingen förändring')}",
                "tooltip_line_10": f"Servicenoder i DeSO: {format_sv(values.get('antal_servicenoder', 0))}",
            }
            geometry = feature["geometry"]
            polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
            for polygon in polygons:
                deso_rows.append({**row, "polygon": polygon[0]})
        layers.append(
            pdk.Layer(
                "PolygonLayer", id="deso-bortfallsanalys", data=deso_rows,
                get_polygon="polygon", get_fill_color="fill_color",
                get_line_color="line_color", line_width_min_pixels=1.2,
                stroked=True, filled=True, pickable=True, auto_highlight=True,
            )
        )
    if map_mode in {"1 km-rutor", "Båda"}:
        layers.append(grid_layer)

    remaining_nodes = nodes if not removed_ids else nodes.loc[
        ~nodes["kluster_id"].isin(removed_ids)
    ]
    node_layer = pdk.Layer(
        "ScatterplotLayer",
        id="kvarvarande-servicenoder",
        data=remaining_nodes,
        get_position="[lon, lat]",
        get_fill_color=[52, 92, 125, 215],
        get_line_color=[255, 255, 255, 230],
        get_radius=420,
        radius_min_pixels=3,
        radius_max_pixels=7,
        line_width_min_pixels=1,
        stroked=True,
        pickable=False,
    )
    removed_layer = None
    if removed_ids:
        removed_layer = pdk.Layer(
            "ScatterplotLayer", id="simulerat-bortfall",
            data=nodes.loc[nodes["kluster_id"].isin(removed_ids)],
            get_position="[lon, lat]", get_fill_color=[255, 255, 255, 245],
            get_line_color=[105, 28, 45, 255], get_radius=850,
            radius_min_pixels=8, radius_max_pixels=15,
            line_width_min_pixels=4, stroked=True, pickable=False,
        )
    view_frame = accessibility[["lon", "lat"]]
    layers.extend([_municipality_boundary_layer(municipality_codes), node_layer])
    if removed_layer is not None:
        layers.append(removed_layer)
    return pdk.Deck(
        map_style=None,
        initial_view_state=_map_view(view_frame),
        layers=layers,
        tooltip={
            "html": "<b>{tooltip_title}</b><br>{tooltip_line_1}<br>"
            "{tooltip_line_2}<br>{tooltip_line_3}<br>{tooltip_line_4}<br>"
            "{tooltip_line_5}<br>{tooltip_line_6}<br>{tooltip_line_7}<br>"
            "{tooltip_line_8}<br>{tooltip_line_9}<br>{tooltip_line_10}",
            "style": {
                "backgroundColor": "#26323d",
                "color": "white",
                "fontSize": "12px",
            },
        },
    )


def make_deso_map(
    geojson: dict,
    metric: str,
    metric_label: str,
    nodes: pd.DataFrame | None = None,
    municipality_codes: set[str] | None = None,
    place_areas: dict | None = None,
    place_types: set[str] | None = None,
) -> pdk.Deck:
    """Skapa en DeSO-karta med robust färgskala och frivill nodöverlagring."""
    selected_features = [
        feature
        for feature in geojson["features"]
        if not municipality_codes
        or str(feature["properties"]["kommunkod"]) in municipality_codes
    ]
    values = np.array(
        [float(feature["properties"].get(metric) or 0) for feature in selected_features]
    )
    lower, upper = np.quantile(values, [0.05, 0.95]) if len(values) else (0.0, 1.0)
    if upper <= lower:
        upper = lower + 1.0

    map_features = []
    for feature in selected_features:
        properties = dict(feature["properties"])
        value = float(properties.get(metric) or 0)
        scaled = max(0.0, min(1.0, (value - lower) / (upper - lower)))
        properties["fill_color"] = [
            int(235 - 205 * scaled),
            int(238 - 95 * scaled),
            int(224 - 55 * scaled),
            175,
        ]
        properties["kommunnamn"] = DALARNA_MUNICIPALITY_NAMES.get(
            str(properties["kommunkod"]), str(properties["kommunkod"])
        )
        properties["kartmatt"] = (
            f"{value * 100:.1f} %" if metric.startswith("andel_") else f"{value:,.1f}"
        ).replace(",", " ").replace(".", ",")
        properties["befolkning_text"] = f"{int(properties['befolkning_2024']):,}".replace(",", " ")
        properties["aldre_text"] = f"{float(properties['andel_65_plus_2024']) * 100:.1f} %".replace(".", ",")
        map_features.append(
            {
                "type": "Feature",
                "id": feature.get("id"),
                "properties": properties,
                "geometry": feature["geometry"],
            }
        )
    map_geojson = {"type": "FeatureCollection", "features": map_features}
    polygon_layer = pdk.Layer(
        "GeoJsonLayer",
        id="deso-omraden",
        data=map_geojson,
        get_fill_color="properties.fill_color",
        get_line_color=[255, 255, 255, 190],
        line_width_min_pixels=0.7,
        stroked=True,
        filled=True,
        pickable=True,
    )
    layers: list[pdk.Layer] = [polygon_layer]
    if place_areas and place_types:
        place_colors = {
            "Tätort": ([49, 94, 170, 70], [30, 66, 132, 220]),
            "Småort": ([35, 145, 116, 75], [20, 105, 82, 220]),
            "Fritidshusområde": ([145, 91, 168, 70], [107, 57, 131, 220]),
        }
        overlay_features = []
        for feature in place_areas["features"]:
            properties = dict(feature["properties"])
            if properties["omradestyp"] not in place_types:
                continue
            if municipality_codes and str(properties["kommunkod"]) not in municipality_codes:
                continue
            fill_color, line_color = place_colors[properties["omradestyp"]]
            properties["fill_color"] = fill_color
            properties["line_color"] = line_color
            overlay_features.append(
                {
                    "type": "Feature",
                    "properties": properties,
                    "geometry": feature["geometry"],
                }
            )
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                id="scb-platsomraden",
                data={"type": "FeatureCollection", "features": overlay_features},
                get_fill_color="properties.fill_color",
                get_line_color="properties.line_color",
                line_width_min_pixels=1.4,
                stroked=True,
                filled=True,
                pickable=False,
            )
        )
    layers.append(_municipality_boundary_layer(municipality_codes))
    view_frame = nodes if nodes is not None else pd.DataFrame()
    if nodes is not None and not nodes.empty:
        node_data = nodes.dropna(subset=["lon", "lat"]).copy()
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                id="servicenoder-over-deso",
                data=node_data,
                get_position="[lon, lat]",
                get_fill_color=[95, 104, 115, 225],
                get_line_color=[255, 255, 255, 240],
                get_radius=420,
                radius_min_pixels=3,
                radius_max_pixels=8,
                line_width_min_pixels=1,
                stroked=True,
                pickable=False,
            )
        )
    if view_frame.empty:
        view_state = pdk.ViewState(latitude=61.0, longitude=14.5, zoom=6.3)
    else:
        view_state = _map_view(view_frame)
    return pdk.Deck(
        map_style=None,
        initial_view_state=view_state,
        layers=layers,
        tooltip={
            "text": "{properties.desokod} · {properties.kommunnamn}\n"
            + f"{metric_label}: "
            + "{properties.kartmatt}\n"
            "Befolkning: {properties.befolkning_text}\n"
            "65 år eller äldre: {properties.aldre_text}\n"
            "Servicenoder i området: {properties.antal_servicenoder}"
        },
    )


def municipality_offer_node_counts(
    service: pd.DataFrame, nodes: pd.DataFrame
) -> pd.DataFrame:
    offers = service.groupby("kommun").size().rename("Aktörstjänster")
    physical = nodes.groupby("kommun").size().rename("Adress-/servicenoder")
    return (
        pd.concat([physical, offers], axis=1)
        .fillna(0)
        .reset_index()
        .rename(columns={"kommun": "Kommun"})
        .sort_values("Adress-/servicenoder", ascending=False)
    )
