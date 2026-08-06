"""Datainläsning och härledning för projektets Streamlit-dashboard."""

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer


PACKAGE_FILENAME = "Paketvolymer_2024_Dalarna_kommun.xlsx"
SERVICE_FILENAME = "Servicepunkter_2026_Dalarna.xlsx"


def resolve_data_directory(project_root: Path) -> Path:
    """Hitta den primära datamappen, med den äldre projektkopian som reserv."""
    candidates = [
        project_root / "data" / "raw",
        project_root / "karin_lovgren_dalarna" / "rawdata",
    ]
    for candidate in candidates:
        if (candidate / PACKAGE_FILENAME).exists() and (
            candidate / SERVICE_FILENAME
        ).exists():
            return candidate
    raise FileNotFoundError(
        "Hittade inte projektets två Excel-filer i data/raw eller "
        "karin_lovgren_dalarna/rawdata."
    )


def read_package_volumes(data_dir: Path) -> pd.DataFrame:
    """Läs och normalisera kommunala paketvolymer (angivna i tusental)."""
    packages = pd.read_excel(data_dir / PACKAGE_FILENAME, header=2)
    packages = packages.loc[packages["Kommun"].notna()].copy()
    packages = packages.loc[packages["Kommun"].str.casefold() != "summa"].copy()
    packages = packages.rename(
        columns={
            "Kommun": "kommun",
            "Paketbrev": "paketbrev_tusen",
            "B2C": "b2c_tusen",
            "C2X": "c2x_tusen",
            "B2B": "b2b_tusen",
        }
    )
    volume_columns = [
        "paketbrev_tusen",
        "b2c_tusen",
        "c2x_tusen",
        "b2b_tusen",
    ]
    packages[volume_columns] = packages[volume_columns].apply(
        pd.to_numeric, errors="coerce"
    )
    packages["total_paket_tusen"] = packages[volume_columns].sum(axis=1)
    return packages.reset_index(drop=True)


def read_service_points(data_dir: Path) -> pd.DataFrame:
    """Läs servicepunkter och omvandla SWEREF 99 TM till WGS84."""
    service = pd.read_excel(data_dir / SERVICE_FILENAME, sheet_name="sp2026")
    service.columns = [
        str(column).replace("\r\n", "\n") for column in service.columns
    ]
    service = service.rename(
        columns={
            "Aktör": "aktor",
            "OMBUD/BENÄMNING": "ombud",
            "ADRESS": "adress_original",
            "ORT": "ort_original",
            "Typ av servicepunkt": "typ_servicepunkt",
            "Leveransfrekvens \n(dgr/vecka)": "leveransdagar_per_vecka",
            "Kn_typ": "kommuntyp",
            "Befolkning kn": "befolkning_kn",
            "Arbetsställen": "arbetsstallen",
            "Totalt antal avlämnings-ställen (kn)": "avlamningsstallen_kn",
            "enskild/\nkluster": "klusterstatus",
        }
    )

    for column in [
        "leveransdagar_per_vecka",
        "e",
        "n",
        "befolkning_kn",
        "arbetsstallen",
    ]:
        service[column] = pd.to_numeric(service[column], errors="coerce")

    service["lon"] = pd.NA
    service["lat"] = pd.NA
    valid_coordinates = service["e"].notna() & service["n"].notna()
    if valid_coordinates.any():
        transformer = Transformer.from_crs(3006, 4326, always_xy=True)
        lon, lat = transformer.transform(
            service.loc[valid_coordinates, "e"].to_numpy(),
            service.loc[valid_coordinates, "n"].to_numpy(),
        )
        service.loc[valid_coordinates, "lon"] = lon
        service.loc[valid_coordinates, "lat"] = lat

    service["lon"] = pd.to_numeric(service["lon"], errors="coerce")
    service["lat"] = pd.to_numeric(service["lat"], errors="coerce")
    return service.reset_index(drop=True)


def read_clusters(data_dir: Path) -> pd.DataFrame:
    """Läs arbetsbokens aggregerade klusterblad."""
    clusters = pd.read_excel(data_dir / SERVICE_FILENAME, sheet_name="Kluster")
    clusters.columns = [
        str(column).replace("\r\n", "\n") for column in clusters.columns
    ]
    return clusters


def _join_unique(values: pd.Series) -> str:
    """Sammanfoga unika, ifyllda textvärden i stabil ordning."""
    unique = sorted({str(value).strip() for value in values.dropna() if str(value).strip()})
    return "; ".join(unique)


def build_service_nodes(
    service: pd.DataFrame, clusters: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Gruppera aktörsrader till fysiska servicenoder och beräkna nodgleshet.

    ``kluster_id`` är i källfilen 1–1 med både ``uuidadrpl`` och koordinatpar.
    En nod kan däremot innehålla flera aktörer och servicetyper.
    """
    nodes = (
        service.groupby("kluster_id", as_index=False)
        .agg(
            uuidadrpl=("uuidadrpl", "first"),
            nodnamn_fallback=(
                "ombud",
                lambda values: next(
                    (str(v) for v in values if pd.notna(v)), "Namnlös nod"
                ),
            ),
            adress_fallback=("adress", "first"),
            postnummer_fallback=("postnummer", "first"),
            postort_fallback=("postort", "first"),
            kommun_fallback=("kommun", "first"),
            kommuntyp_fallback=("kommuntyp", "first"),
            e=("e", "first"),
            n=("n", "first"),
            lon=("lon", "first"),
            lat=("lat", "first"),
            aktorstjanster=("DB_ID_2026", "count"),
            antal_aktorer=("aktor", "nunique"),
            aktorer=("aktor", _join_unique),
            antal_servicetyper=("typ_servicepunkt", "nunique"),
            servicetyper=("typ_servicepunkt", _join_unique),
            median_leveransdagar_per_vecka=("leveransdagar_per_vecka", "median"),
            min_leveransdagar_per_vecka=("leveransdagar_per_vecka", "min"),
            max_leveransdagar_per_vecka=("leveransdagar_per_vecka", "max"),
            antal_kanda_leveransfrekvenser=("leveransdagar_per_vecka", "count"),
            befolkning_kn=("befolkning_kn", "max"),
            arbetsstallen=("arbetsstallen", "max"),
            avlamningsstallen_kn=("avlamningsstallen_kn", "max"),
        )
    )
    if clusters is not None:
        node_dimension = clusters[
            [
                "kluster_id",
                "kluster_namn",
                "uuidadrpl_kluster",
                "Adress",
                "postnummer",
                "postort",
                "kommun",
                "kn_typ",
            ]
        ].rename(
            columns={
                "kluster_namn": "nodnamn",
                "uuidadrpl_kluster": "uuidadrpl_dimension",
                "Adress": "adress",
                "kn_typ": "kommuntyp",
            }
        )
        nodes = node_dimension.merge(
            nodes, on="kluster_id", how="left", validate="1:1"
        )
        if not nodes["uuidadrpl_dimension"].equals(nodes["uuidadrpl"]):
            raise ValueError("UUID matchar inte 1:1 mellan Kluster och sp2026.")
        nodes = nodes.drop(columns="uuidadrpl_dimension")
        for canonical, fallback in [
            ("nodnamn", "nodnamn_fallback"),
            ("adress", "adress_fallback"),
            ("postnummer", "postnummer_fallback"),
            ("postort", "postort_fallback"),
            ("kommun", "kommun_fallback"),
            ("kommuntyp", "kommuntyp_fallback"),
        ]:
            nodes[canonical] = nodes[canonical].fillna(nodes[fallback])
    else:
        nodes = nodes.rename(
            columns={
                "nodnamn_fallback": "nodnamn",
                "adress_fallback": "adress",
                "postnummer_fallback": "postnummer",
                "postort_fallback": "postort",
                "kommun_fallback": "kommun",
                "kommuntyp_fallback": "kommuntyp",
            }
        )
    nodes = nodes.drop(
        columns=[column for column in nodes if column.endswith("_fallback")]
    )
    nodes["en_aktor"] = nodes["antal_aktorer"].eq(1)
    nodes["leveransfrekvens_saknas"] = nodes[
        "antal_kanda_leveransfrekvenser"
    ].eq(0)

    coordinates = nodes[["e", "n"]].to_numpy(dtype=float)
    delta = coordinates[:, None, :] - coordinates[None, :, :]
    distances = np.sqrt(np.square(delta).sum(axis=2))
    np.fill_diagonal(distances, np.inf)
    nearest_positions = distances.argmin(axis=1)
    nodes["narmaste_annan_nod_km"] = distances.min(axis=1) / 1_000
    nodes["narmaste_annan_nod_id"] = nodes.iloc[nearest_positions][
        "kluster_id"
    ].to_numpy()
    # Källans kluster behålls oförändrade. Mycket närliggande separata kluster
    # flaggas för manuell kvalitetskontroll, inte automatisk sammanslagning.
    nodes["qa_nara_annan_nod_under_25m"] = nodes[
        "narmaste_annan_nod_km"
    ].lt(0.025)

    actor_sets = [set(value.split("; ")) for value in nodes["aktorer"]]
    different_actor_distances: list[float] = []
    for index, actors in enumerate(actor_sets):
        candidates = [
            position
            for position, candidate_actors in enumerate(actor_sets)
            if position != index and bool(candidate_actors - actors)
        ]
        if candidates:
            different_actor_distances.append(
                float(distances[index, candidates].min() / 1_000)
            )
        else:
            different_actor_distances.append(float("nan"))
    nodes["narmaste_nod_med_annan_aktor_km"] = different_actor_distances
    return nodes.sort_values(["kommun", "postort", "nodnamn"]).reset_index(drop=True)


def build_municipality_profile(
    packages: pd.DataFrame,
    service: pd.DataFrame,
    clusters: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Bygg kommunmått för både aktörstjänster och fysiska noder."""
    nodes = build_service_nodes(service, clusters)
    offer_summary = (
        service.groupby("kommun", as_index=False)
        .agg(
            aktorstjanster=("DB_ID_2026", "count"),
            aktorer=("aktor", "nunique"),
            typer_servicepunkt=("typ_servicepunkt", "nunique"),
            median_leveransdagar_per_vecka=(
                "leveransdagar_per_vecka",
                "median",
            ),
            befolkning_kn=("befolkning_kn", "max"),
            arbetsstallen=("arbetsstallen", "max"),
            kommuntyp=("kommuntyp", "first"),
        )
    )
    node_summary = (
        nodes.groupby("kommun", as_index=False)
        .agg(
            servicenoder=("kluster_id", "count"),
            enaktor_noder=("en_aktor", "sum"),
            noder_utan_kand_leveransfrekvens=("leveransfrekvens_saknas", "sum"),
            median_narmaste_nod_km=("narmaste_annan_nod_km", "median"),
            max_narmaste_nod_km=("narmaste_annan_nod_km", "max"),
            median_aktorer_per_nod=("antal_aktorer", "median"),
        )
    )
    service_summary = offer_summary.merge(
        node_summary, on="kommun", how="outer", validate="1:1"
    )
    profile = packages.merge(
        service_summary, on="kommun", how="outer", validate="1:1"
    )
    # Bakåtkompatibelt fältnamn. Nya analyser ska använda de uttryckliga
    # kolumnerna ``aktorstjanster`` och ``servicenoder``.
    profile["servicepunkter"] = profile["aktorstjanster"]
    profile["b2c_tusen_per_servicepunkt"] = (
        profile["b2c_tusen"] / profile["aktorstjanster"]
    )
    profile["total_paket_tusen_per_servicepunkt"] = (
        profile["total_paket_tusen"] / profile["aktorstjanster"]
    )
    profile["servicepunkter_per_10000_inv"] = (
        profile["aktorstjanster"] / profile["befolkning_kn"] * 10_000
    )
    profile["b2c_tusen_per_servicenod"] = (
        profile["b2c_tusen"] / profile["servicenoder"]
    )
    profile["total_paket_tusen_per_servicenod"] = (
        profile["total_paket_tusen"] / profile["servicenoder"]
    )
    profile["servicenoder_per_10000_inv"] = (
        profile["servicenoder"] / profile["befolkning_kn"] * 10_000
    )
    profile["andel_enaktor_noder"] = (
        profile["enaktor_noder"] / profile["servicenoder"]
    )
    profile["andel_noder_utan_kand_leveransfrekvens"] = (
        profile["noder_utan_kand_leveransfrekvens"] / profile["servicenoder"]
    )
    return profile.sort_values("kommun").reset_index(drop=True)


def add_screening_dimensions(profile: pd.DataFrame) -> pd.DataFrame:
    """Lägg till fyra separata, relativa screeningdimensioner (0–100).

    Måtten är percentilrankningar inom Dalarnas 15 kommuner. De ska användas
    för prioritering av vidare granskning, inte som ett sammanslaget riskindex.
    """
    result = profile.copy()
    result["screening_efterfragetryck"] = (
        result["b2c_tusen_per_servicenod"].rank(pct=True) * 100
    )
    result["screening_nodgleshet"] = (
        result["median_narmaste_nod_km"].rank(pct=True) * 100
    )
    result["screening_aktorberoende"] = (
        result["andel_enaktor_noder"].rank(pct=True) * 100
    )
    known_delivery = result["median_leveransdagar_per_vecka"].rank(pct=True)
    unknown_delivery = result[
        "andel_noder_utan_kand_leveransfrekvens"
    ].rank(pct=True)
    result["screening_leveransunderlag"] = (
        (0.65 * (1 - known_delivery) + 0.35 * unknown_delivery) * 100
    )
    return result


def rank_comparable_deso(
    areas: pd.DataFrame, target_code: str, limit: int = 5
) -> pd.DataFrame:
    """Rangordna en första, transparent statistisk DeSO-likhet.

    Likheten bygger på fyra lika viktade, standardiserade attribut: logaritmerad
    befolkning, logaritmerad befolkningstäthet, andel 65+ och logaritmerat antal
    servicenoder. Resultatet är ett urval för manuell granskning, inte belägg för
    att områdena delar förändringshistoria eller funktionellt omland.
    """
    required = {
        "desokod",
        "befolkning_2024",
        "befolkning_per_km2_2024",
        "andel_65_plus_2024",
        "antal_servicenoder",
    }
    missing = required - set(areas.columns)
    if missing:
        raise ValueError(f"DeSO-tabellen saknar kolumner: {sorted(missing)}")
    work = areas.dropna(subset=list(required)).copy()
    if target_code not in set(work["desokod"]):
        raise ValueError(f"Mål-DeSO {target_code} saknas i underlaget.")

    features = pd.DataFrame(
        {
            "log_befolkning": np.log1p(work["befolkning_2024"]),
            "log_tathet": np.log1p(work["befolkning_per_km2_2024"]),
            "andel_65_plus": work["andel_65_plus_2024"],
            "log_servicenoder": np.log1p(work["antal_servicenoder"]),
        },
        index=work.index,
    )
    scale = features.std(ddof=0).replace(0, 1)
    standardized = (features - features.mean()) / scale
    target_index = work.index[work["desokod"].eq(target_code)][0]
    work["likhetsavstand"] = np.sqrt(
        np.square(standardized - standardized.loc[target_index]).mean(axis=1)
    )
    return (
        work.loc[work["desokod"].ne(target_code)]
        .nsmallest(limit, "likhetsavstand")
        .reset_index(drop=True)
    )


def calculate_grid_accessibility(
    grid: pd.DataFrame,
    nodes: pd.DataFrame,
    removed_node_id: int | None = None,
    removed_node_ids: tuple[int, ...] | list[int] | set[int] | None = None,
    thresholds_km: tuple[float, float, float, float] = (5, 10, 20, 30),
) -> pd.DataFrame:
    """Beräkna närmaste nod före och efter ett eller flera hypotetiska bortfall.

    Avståndet är euklidiskt i SWEREF 99 TM och ska därför tolkas som en
    transparent screening, inte vägavstånd eller restid.
    """
    required_grid = {
        "rutid",
        "e",
        "n",
        "befolkning_2025",
        "befolkning_65_plus_2025",
    }
    required_nodes = {"kluster_id", "e", "n", "nodnamn"}
    if missing := required_grid - set(grid.columns):
        raise ValueError(f"Rutunderlaget saknar kolumner: {sorted(missing)}")
    if missing := required_nodes - set(nodes.columns):
        raise ValueError(f"Nodunderlaget saknar kolumner: {sorted(missing)}")
    if len(thresholds_km) != 4 or any(
        current <= 0 or current >= following
        for current, following in zip(thresholds_km, thresholds_km[1:])
    ):
        raise ValueError("Avståndsgränserna måste vara fyra strikt stigande positiva tal.")

    work = grid.dropna(subset=["e", "n"]).copy().reset_index(drop=True)
    node_work = nodes.dropna(subset=["e", "n"]).copy().reset_index(drop=True)
    if work.empty or node_work.empty:
        raise ValueError("Rut- och nodunderlagen måste innehålla koordinater.")

    def nearest(reference_nodes: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        if reference_nodes.empty:
            raise ValueError("Scenariot måste ha minst en kvarvarande servicenod.")
        grid_coordinates = work[["e", "n"]].to_numpy(dtype=float)
        node_coordinates = reference_nodes[["e", "n"]].to_numpy(dtype=float)
        distances = np.sqrt(
            np.square(grid_coordinates[:, None, :] - node_coordinates[None, :, :]).sum(
                axis=2
            )
        )
        positions = distances.argmin(axis=1)
        return (
            distances[np.arange(len(work)), positions] / 1_000,
            reference_nodes.iloc[positions]["kluster_id"].to_numpy(),
        )

    removed_ids = set(int(value) for value in (removed_node_ids or ()))
    if removed_node_id is not None:
        removed_ids.add(int(removed_node_id))

    before_distance, before_id = nearest(node_work)
    if not removed_ids:
        after_distance, after_id = before_distance.copy(), before_id.copy()
    else:
        unknown_ids = removed_ids - set(node_work["kluster_id"].astype(int))
        if unknown_ids:
            raise ValueError(f"Noder saknas i nodunderlaget: {sorted(unknown_ids)}")
        scenario_nodes = node_work.loc[~node_work["kluster_id"].isin(removed_ids)]
        after_distance, after_id = nearest(scenario_nodes)

    limits = np.asarray(thresholds_km, dtype=float)
    before_class = np.searchsorted(limits, before_distance, side="left")
    after_class = np.searchsorted(limits, after_distance, side="left")
    node_names = node_work.set_index("kluster_id")["nodnamn"].to_dict()

    work["avstand_fore_km"] = before_distance
    work["narmaste_nod_fore_id"] = before_id.astype(int)
    work["narmaste_nod_fore"] = work["narmaste_nod_fore_id"].map(node_names)
    work["avstand_efter_km"] = after_distance
    work["narmaste_nod_efter_id"] = after_id.astype(int)
    work["narmaste_nod_efter"] = work["narmaste_nod_efter_id"].map(node_names)
    work["avstandsokning_km"] = np.maximum(after_distance - before_distance, 0)
    work["klass_fore"] = before_class.astype(int)
    work["klass_efter"] = after_class.astype(int)
    work["paverkad"] = work["narmaste_nod_fore_id"].ne(
        work["narmaste_nod_efter_id"]
    )
    work["samre_avstandsklass"] = after_class > before_class
    return work


def calculate_grid_service_options(
    grid: pd.DataFrame,
    nodes: pd.DataFrame,
) -> pd.DataFrame:
    """Beräkna första nod, andra nod och närmaste nod med alternativ aktör.

    En alternativ aktörsnod erbjuder minst en aktör som inte finns vid rutans
    närmaste nod. Avstånden är euklidiska i SWEREF 99 TM och ska användas som
    transparent screening, inte som vägavstånd eller restid.
    """
    required_grid = {
        "rutid",
        "e",
        "n",
        "befolkning_2025",
        "befolkning_65_plus_2025",
    }
    required_nodes = {"kluster_id", "e", "n", "nodnamn", "aktorer"}
    if missing := required_grid - set(grid.columns):
        raise ValueError(f"Rutunderlaget saknar kolumner: {sorted(missing)}")
    if missing := required_nodes - set(nodes.columns):
        raise ValueError(f"Nodunderlaget saknar kolumner: {sorted(missing)}")

    work = grid.dropna(subset=["e", "n"]).copy().reset_index(drop=True)
    node_work = nodes.dropna(subset=["e", "n"]).copy().reset_index(drop=True)
    if work.empty or len(node_work) < 2:
        raise ValueError("Rutunderlaget måste ha koordinater och nätet minst två noder.")

    grid_coordinates = work[["e", "n"]].to_numpy(dtype=float)
    node_coordinates = node_work[["e", "n"]].to_numpy(dtype=float)
    distances = np.sqrt(
        np.square(grid_coordinates[:, None, :] - node_coordinates[None, :, :]).sum(
            axis=2
        )
    ) / 1_000

    nearest_two = np.argpartition(distances, kth=1, axis=1)[:, :2]
    nearest_two_distances = np.take_along_axis(distances, nearest_two, axis=1)
    order = np.argsort(nearest_two_distances, axis=1)
    nearest_two = np.take_along_axis(nearest_two, order, axis=1)
    first_positions = nearest_two[:, 0]
    second_positions = nearest_two[:, 1]
    row_positions = np.arange(len(work))

    node_ids = node_work["kluster_id"].astype(int).to_numpy()
    node_names = node_work["nodnamn"].astype(str).to_numpy()
    node_actors = node_work["aktorer"].fillna("").astype(str).to_numpy()
    actor_sets = [
        {actor.strip() for actor in value.split(";") if actor.strip()}
        for value in node_actors
    ]

    alternative_positions = np.full(len(work), -1, dtype=int)
    alternative_distances = np.full(len(work), np.nan, dtype=float)
    for first_position in np.unique(first_positions):
        row_mask = first_positions == first_position
        first_actors = actor_sets[int(first_position)]
        candidate_positions = np.asarray(
            [
                position
                for position, candidate_actors in enumerate(actor_sets)
                if position != first_position and bool(candidate_actors - first_actors)
            ],
            dtype=int,
        )
        if not len(candidate_positions):
            continue
        candidate_distances = distances[row_mask][:, candidate_positions]
        local_positions = candidate_distances.argmin(axis=1)
        alternative_positions[row_mask] = candidate_positions[local_positions]
        alternative_distances[row_mask] = candidate_distances[
            np.arange(int(row_mask.sum())), local_positions
        ]

    first_distances = distances[row_positions, first_positions]
    second_distances = distances[row_positions, second_positions]
    work["forsta_nod_id"] = node_ids[first_positions]
    work["forsta_nod"] = node_names[first_positions]
    work["forsta_nod_aktorer"] = node_actors[first_positions]
    work["forsta_nod_en_aktor"] = [
        len(actor_sets[position]) == 1 for position in first_positions
    ]
    work["avstand_forsta_nod_km"] = first_distances
    work["andra_nod_id"] = node_ids[second_positions]
    work["andra_nod"] = node_names[second_positions]
    work["andra_nod_aktorer"] = node_actors[second_positions]
    work["avstand_andra_nod_km"] = second_distances
    work["redundansgap_km"] = np.maximum(second_distances - first_distances, 0)

    valid_alternative = alternative_positions >= 0
    work["alternativ_aktor_nod_id"] = pd.array(
        [
            node_ids[position] if valid else pd.NA
            for position, valid in zip(alternative_positions, valid_alternative)
        ],
        dtype="Int64",
    )
    work["alternativ_aktor_nod"] = [
        node_names[position] if valid else "Saknas i underlaget"
        for position, valid in zip(alternative_positions, valid_alternative)
    ]
    work["alternativ_aktor_nod_aktorer"] = [
        node_actors[position] if valid else ""
        for position, valid in zip(alternative_positions, valid_alternative)
    ]
    work["nya_aktorer_vid_alternativ"] = [
        "; ".join(sorted(actor_sets[position] - actor_sets[first_position]))
        if valid else ""
        for first_position, position, valid in zip(
            first_positions, alternative_positions, valid_alternative
        )
    ]
    work["avstand_alternativ_aktor_km"] = alternative_distances
    work["alternativ_aktor_tillagg_km"] = np.maximum(
        alternative_distances - first_distances, 0
    )
    return work


def _weighted_quantile(
    values: pd.Series,
    weights: pd.Series,
    quantile: float,
) -> float:
    """Beräkna viktad kvantil för ändliga värden och icke-negativa vikter."""
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return float("nan")
    ordered = pd.DataFrame(
        {"value": values.loc[valid].astype(float), "weight": weights.loc[valid].astype(float)}
    ).sort_values("value")
    cumulative = ordered["weight"].cumsum()
    target = float(quantile) * float(ordered["weight"].sum())
    return float(ordered.loc[cumulative.ge(target), "value"].iloc[0])


def aggregate_grid_service_options_by_municipality(
    grid_options: pd.DataFrame,
) -> pd.DataFrame:
    """Summera rutmått befolkningsviktat till kommun och lägg till percentiler."""
    required = {
        "kommunkod",
        "befolkning_2025",
        "befolkning_65_plus_2025",
        "avstand_forsta_nod_km",
        "avstand_andra_nod_km",
        "redundansgap_km",
        "avstand_alternativ_aktor_km",
        "forsta_nod_en_aktor",
    }
    if missing := required - set(grid_options.columns):
        raise ValueError(f"Rutresultatet saknar kolumner: {sorted(missing)}")

    group_columns = ["kommunkod"]
    if "kommun" in grid_options.columns:
        group_columns.append("kommun")

    rows: list[dict[str, object]] = []
    for group_key, frame in grid_options.groupby(group_columns, dropna=False):
        keys = group_key if isinstance(group_key, tuple) else (group_key,)
        row = dict(zip(group_columns, keys))
        population = frame["befolkning_2025"].astype(float)
        population_total = float(population.sum())

        def weighted_mean(column: str) -> float:
            values = pd.to_numeric(frame[column], errors="coerce")
            valid = values.notna() & population.gt(0)
            if not valid.any():
                return float("nan")
            return float(np.average(values.loc[valid], weights=population.loc[valid]))

        def population_share(mask: pd.Series) -> float:
            if population_total <= 0:
                return float("nan")
            return float(population.loc[mask.fillna(False)].sum() / population_total)

        row.update(
            {
                "befolkning_2025": int(population_total),
                "befolkning_65_plus_2025": int(
                    frame["befolkning_65_plus_2025"].sum()
                ),
                "befolkade_rutor": int(len(frame)),
                "befolkningsvagt_forsta_nod_km": weighted_mean(
                    "avstand_forsta_nod_km"
                ),
                "p90_forsta_nod_km": _weighted_quantile(
                    frame["avstand_forsta_nod_km"], population, 0.9
                ),
                "andel_over_10_km_forsta_nod": population_share(
                    frame["avstand_forsta_nod_km"].gt(10)
                ),
                "befolkningsvagt_andra_nod_km": weighted_mean(
                    "avstand_andra_nod_km"
                ),
                "befolkningsvagt_redundansgap_km": weighted_mean(
                    "redundansgap_km"
                ),
                "andel_over_20_km_andra_nod": population_share(
                    frame["avstand_andra_nod_km"].gt(20)
                ),
                "befolkningsvagt_alternativ_aktor_km": weighted_mean(
                    "avstand_alternativ_aktor_km"
                ),
                "andel_over_20_km_alternativ_aktor": population_share(
                    frame["avstand_alternativ_aktor_km"].gt(20)
                ),
                "andel_befolkning_narmast_enaktorsnod": population_share(
                    frame["forsta_nod_en_aktor"].astype(bool)
                ),
            }
        )
        rows.append(row)

    result = pd.DataFrame(rows).sort_values("kommunkod").reset_index(drop=True)
    score_sources = {
        "screening_forsta_nod": "befolkningsvagt_forsta_nod_km",
        "screening_andra_nod": "befolkningsvagt_andra_nod_km",
        "screening_alternativ_aktor": "befolkningsvagt_alternativ_aktor_km",
        "screening_redundansgap": "befolkningsvagt_redundansgap_km",
    }
    for score_column, source_column in score_sources.items():
        result[score_column] = result[source_column].rank(pct=True) * 100
    return result


def aggregate_grid_accessibility_to_deso(
    accessibility: pd.DataFrame,
    deso_population: pd.DataFrame,
    quality_threshold_pct: float = 5.0,
) -> pd.DataFrame:
    """Summera rutbaserad tillgänglighet till DeSO och jämför årgångarna.

    Scenarioresultatet använder genomgående rutbefolkning 2025. DeSO:s
    publicerade befolkning 2024 behålls som en separat kvalitetsjämförelse.
    """
    required_grid = {
        "desokod",
        "kommun",
        "befolkning_2025",
        "befolkning_65_plus_2025",
        "paverkad",
        "samre_avstandsklass",
        "avstandsokning_km",
        "klass_efter",
        "narmaste_nod_efter",
    }
    required_deso = {
        "desokod",
        "kommun",
        "befolkning_2024",
        "befolkning_65_plus_2024",
        "antal_servicenoder",
    }
    if missing := required_grid - set(accessibility.columns):
        raise ValueError(f"Rutresultatet saknar kolumner: {sorted(missing)}")
    if missing := required_deso - set(deso_population.columns):
        raise ValueError(f"DeSO-underlaget saknar kolumner: {sorted(missing)}")
    if quality_threshold_pct < 0:
        raise ValueError("Kvalitetsgränsen får inte vara negativ.")

    work = accessibility.copy()
    work["berord_befolkning"] = (
        work["befolkning_2025"] * work["paverkad"].astype(int)
    )
    work["berord_befolkning_65_plus"] = (
        work["befolkning_65_plus_2025"] * work["paverkad"].astype(int)
    )
    work["samre_klass_befolkning"] = (
        work["befolkning_2025"] * work["samre_avstandsklass"].astype(int)
    )
    work["over_hogsta_grans_befolkning"] = (
        work["befolkning_2025"] * work["klass_efter"].eq(4).astype(int)
    )
    work["viktad_okning"] = (
        work["avstandsokning_km"] * work["berord_befolkning"]
    )

    grouped = work.groupby("desokod", as_index=False).agg(
        kommun_ruta=("kommun", "first"),
        rutbefolkning_2025=("befolkning_2025", "sum"),
        rutbefolkning_65_plus_2025=("befolkning_65_plus_2025", "sum"),
        befolkade_rutor=("desokod", "size"),
        berord_befolkning=("berord_befolkning", "sum"),
        berord_befolkning_65_plus=("berord_befolkning_65_plus", "sum"),
        berorda_rutor=("paverkad", "sum"),
        samre_klass_befolkning=("samre_klass_befolkning", "sum"),
        over_hogsta_grans_befolkning=("over_hogsta_grans_befolkning", "sum"),
        viktad_okning=("viktad_okning", "sum"),
    )

    affected = work.loc[work["paverkad"]]
    maximum_increase = (
        affected.groupby("desokod")["avstandsokning_km"].max()
        if not affected.empty
        else pd.Series(dtype=float)
    )

    def most_common_alternative(group: pd.DataFrame) -> str:
        weighted = group.groupby("narmaste_nod_efter")["befolkning_2025"].sum()
        return str(weighted.idxmax()) if not weighted.empty else "Ingen förändring"

    alternatives = (
        affected.groupby("desokod").apply(
            most_common_alternative, include_groups=False
        )
        if not affected.empty
        else pd.Series(dtype=str)
    )
    grouped["storsta_avstandsokning_km"] = (
        grouped["desokod"].map(maximum_increase).fillna(0.0)
    )
    grouped["vanligaste_alternativa_nod"] = (
        grouped["desokod"].map(alternatives).fillna("Ingen förändring")
    )
    grouped["befolkningsvagd_avstandsokning_km"] = np.divide(
        grouped["viktad_okning"],
        grouped["berord_befolkning"],
        out=np.zeros(len(grouped), dtype=float),
        where=grouped["berord_befolkning"].to_numpy() > 0,
    )

    published = deso_population[
        [
            "desokod",
            "kommun",
            "befolkning_2024",
            "befolkning_65_plus_2024",
            "antal_servicenoder",
        ]
    ].rename(
        columns={
            "kommun": "kommun_deso",
            "befolkning_2024": "deso_befolkning_2024",
            "befolkning_65_plus_2024": "deso_befolkning_65_plus_2024",
        }
    )
    result = published.merge(grouped, on="desokod", how="left", validate="1:1")
    numeric_columns = [
        "rutbefolkning_2025",
        "rutbefolkning_65_plus_2025",
        "befolkade_rutor",
        "berord_befolkning",
        "berord_befolkning_65_plus",
        "berorda_rutor",
        "samre_klass_befolkning",
        "over_hogsta_grans_befolkning",
        "befolkningsvagd_avstandsokning_km",
        "storsta_avstandsokning_km",
    ]
    result[numeric_columns] = result[numeric_columns].fillna(0)
    result["kommun"] = result["kommun_ruta"].fillna(result["kommun_deso"])
    result["vanligaste_alternativa_nod"] = result[
        "vanligaste_alternativa_nod"
    ].fillna("Ingen förändring")
    result["andel_berord_befolkning"] = np.divide(
        result["berord_befolkning"],
        result["rutbefolkning_2025"],
        out=np.zeros(len(result), dtype=float),
        where=result["rutbefolkning_2025"].to_numpy() > 0,
    )
    result["andel_samre_avstandsklass"] = np.divide(
        result["samre_klass_befolkning"],
        result["rutbefolkning_2025"],
        out=np.zeros(len(result), dtype=float),
        where=result["rutbefolkning_2025"].to_numpy() > 0,
    )
    result["andel_over_hogsta_grans"] = np.divide(
        result["over_hogsta_grans_befolkning"],
        result["rutbefolkning_2025"],
        out=np.zeros(len(result), dtype=float),
        where=result["rutbefolkning_2025"].to_numpy() > 0,
    )
    result["befolkningsdifferens"] = (
        result["rutbefolkning_2025"] - result["deso_befolkning_2024"]
    )
    result["befolkningsdifferens_pct"] = np.divide(
        result["befolkningsdifferens"] * 100,
        result["deso_befolkning_2024"],
        out=np.zeros(len(result), dtype=float),
        where=result["deso_befolkning_2024"].to_numpy() > 0,
    )
    result["absolut_befolkningsdifferens_pct"] = result[
        "befolkningsdifferens_pct"
    ].abs()
    result["aldre_differens"] = (
        result["rutbefolkning_65_plus_2025"]
        - result["deso_befolkning_65_plus_2024"]
    )
    result["kvalitetsflagga"] = result["absolut_befolkningsdifferens_pct"].gt(
        quality_threshold_pct
    )
    result["berort_deso"] = result["berord_befolkning"].gt(0)
    return result.drop(columns=["kommun_ruta", "kommun_deso", "viktad_okning"])


def load_dashboard_data(
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, Path]:
    """Läs alla källor och returnera paket, service, profil, kluster och sökväg."""
    data_dir = resolve_data_directory(project_root)
    packages = read_package_volumes(data_dir)
    service = read_service_points(data_dir)
    clusters = read_clusters(data_dir)
    profile = add_screening_dimensions(
        build_municipality_profile(packages, service, clusters)
    )
    return packages, service, profile, clusters, data_dir
