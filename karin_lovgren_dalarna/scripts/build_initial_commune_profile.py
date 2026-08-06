from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAWDATA = ROOT / "rawdata"
DERIVED = ROOT / "derived"
DOCS = ROOT / "docs"


PACKAGE_FILE = RAWDATA / "Paketvolymer_2024_Dalarna_kommun.xlsx"
SERVICE_FILE = RAWDATA / "Servicepunkter_2026_Dalarna.xlsx"


def clean_package_volumes() -> pd.DataFrame:
    packages = pd.read_excel(PACKAGE_FILE, header=2)
    packages = packages[packages["Kommun"].notna()].copy()
    packages = packages[packages["Kommun"].str.lower() != "summa"].copy()
    packages = packages.rename(
        columns={
            "Kommun": "kommun",
            "Paketbrev": "paketbrev_tusen",
            "B2C": "b2c_tusen",
            "C2X": "c2x_tusen",
            "B2B": "b2b_tusen",
        }
    )
    value_cols = ["paketbrev_tusen", "b2c_tusen", "c2x_tusen", "b2b_tusen"]
    packages[value_cols] = packages[value_cols].apply(pd.to_numeric, errors="coerce")
    packages["total_paket_tusen"] = packages[value_cols].sum(axis=1)
    return packages


def clean_service_points() -> pd.DataFrame:
    service = pd.read_excel(SERVICE_FILE, sheet_name="sp2026")
    service = service.rename(
        columns={
            "Aktör": "aktor",
            "Typ av servicepunkt": "typ_servicepunkt",
            "Leveransfrekvens \n(dgr/vecka)": "leveransdagar_per_vecka",
            "Befolkning kn": "befolkning_kn",
            "Arbetsställen": "arbetsstallen",
            "Totalt antal avlämnings-ställen (kn)": "avlamningsstallen_kn",
            "Avl.stle SBB (kn)": "avlamningsstallen_sbb_kn",
            "Avl.stle LBB (kn)": "avlamningsstallen_lbb_kn",
            "Kn_typ": "kommuntyp",
        }
    )
    service["leveransdagar_per_vecka"] = pd.to_numeric(
        service["leveransdagar_per_vecka"], errors="coerce"
    )
    return service


def first_non_null(series: pd.Series):
    values = series.dropna()
    return values.iloc[0] if not values.empty else pd.NA


def summarize_service_points(service: pd.DataFrame) -> pd.DataFrame:
    grouped = service.groupby("kommun", dropna=False)
    summary = grouped.agg(
        servicepunkter=("DB_ID_2026", "count"),
        aktorer=("aktor", "nunique"),
        typer_servicepunkt=("typ_servicepunkt", "nunique"),
        unika_kluster=("kluster_id", "nunique"),
        median_leveransdagar_per_vecka=("leveransdagar_per_vecka", "median"),
        min_leveransdagar_per_vecka=("leveransdagar_per_vecka", "min"),
        max_leveransdagar_per_vecka=("leveransdagar_per_vecka", "max"),
        befolkning_kn=("befolkning_kn", "max"),
        arbetsstallen=("arbetsstallen", "max"),
        avlamningsstallen_kn=("avlamningsstallen_kn", "max"),
        avlamningsstallen_sbb_kn=("avlamningsstallen_sbb_kn", "max"),
        avlamningsstallen_lbb_kn=("avlamningsstallen_lbb_kn", "max"),
        kommuntyp=("kommuntyp", first_non_null),
    )
    return summary.reset_index()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["b2c_tusen_per_servicepunkt"] = out["b2c_tusen"] / out["servicepunkter"]
    out["total_paket_tusen_per_servicepunkt"] = (
        out["total_paket_tusen"] / out["servicepunkter"]
    )
    out["servicepunkter_per_10000_inv"] = (
        out["servicepunkter"] / out["befolkning_kn"] * 10_000
    )
    out["servicepunkter_per_1000_arbetsstallen"] = (
        out["servicepunkter"] / out["arbetsstallen"] * 1_000
    )
    out["servicepunkter_per_1000_avlamningsstallen"] = (
        out["servicepunkter"] / out["avlamningsstallen_kn"] * 1_000
    )
    out["b2c_tusen_per_1000_avlamningsstallen"] = (
        out["b2c_tusen"] / out["avlamningsstallen_kn"] * 1_000
    )

    # A screening score, not a finished risk model. Higher values mean the
    # municipality should be checked earlier in a qualitative/geographic review.
    high_pressure = out["b2c_tusen_per_servicepunkt"].rank(pct=True)
    low_service_density = 1 - out["servicepunkter_per_10000_inv"].rank(pct=True)
    low_delivery_frequency = 1 - out["median_leveransdagar_per_vecka"].rank(pct=True)
    out["preliminar_screeningpoang"] = (
        0.45 * high_pressure
        + 0.35 * low_service_density
        + 0.20 * low_delivery_frequency
    )
    out["preliminar_screeningrank"] = out["preliminar_screeningpoang"].rank(
        ascending=False, method="min"
    )

    return out


def write_markdown_profile(profile: pd.DataFrame) -> None:
    top_pressure = profile.sort_values(
        "b2c_tusen_per_servicepunkt", ascending=False
    ).head(5)
    top_screening = profile.sort_values("preliminar_screeningrank").head(5)
    low_density = profile.sort_values("servicepunkter_per_10000_inv").head(5)

    def table(df: pd.DataFrame, columns: list[str]) -> str:
        view = df[columns].copy()
        for col in view.columns:
            if pd.api.types.is_float_dtype(view[col]):
                view[col] = view[col].map(lambda value: f"{value:.2f}")
        header = "| " + " | ".join(columns) + " |"
        divider = "| " + " | ".join(["---"] * len(columns)) + " |"
        rows = [
            "| " + " | ".join("" if pd.isna(value) else str(value) for value in row) + " |"
            for row in view.itertuples(index=False, name=None)
        ]
        return "\n".join([header, divider, *rows])

    content = f"""# Första dataprofil: paketvolymer och servicepunkter

Skapad från:

- `rawdata/Paketvolymer_2024_Dalarna_kommun.xlsx`
- `rawdata/Servicepunkter_2026_Dalarna.xlsx`

Paketvolymerna i källfilen anges i tusental. Profilen är en första screening på kommunnivå och ska inte tolkas som ett färdigt riskindex.

## Topp 5: B2C-volym per servicepunkt

{table(top_pressure, ["kommun", "b2c_tusen", "servicepunkter", "b2c_tusen_per_servicepunkt", "kommuntyp"])}

## Topp 5: preliminär screeningpoäng

Screeningpoängen väger samman hög B2C-volym per servicepunkt, låg servicepunktstäthet per invånare och låg medianleveransfrekvens.

{table(top_screening, ["kommun", "preliminar_screeningpoang", "b2c_tusen_per_servicepunkt", "servicepunkter_per_10000_inv", "median_leveransdagar_per_vecka", "kommuntyp"])}

## Lägst servicepunktstäthet per 10 000 invånare

{table(low_density, ["kommun", "servicepunkter", "befolkning_kn", "servicepunkter_per_10000_inv", "kommuntyp"])}

## Att kontrollera före tolkning

- Om servicepunktskoordinaterna ska tolkas som SWEREF 99 TM eller annat koordinatsystem.
- Om paketvolymerna ska behandlas som årsvolym i tusental för samtliga kategorier.
- Om varje rad i `sp2026` ska räknas som en separat servicepunkt, eller om vissa rader bör klustras innan nyckeltal tas fram.
- Om kommunnivå är tillräckligt för första prioritering, eller om analysen snabbt bör gå över till postort, kluster eller restidsområden.
"""
    DOCS.mkdir(exist_ok=True)
    (DOCS / "forsta_dataprofil.md").write_text(content, encoding="utf-8")


def main() -> None:
    DERIVED.mkdir(exist_ok=True)
    packages = clean_package_volumes()
    service = clean_service_points()
    service_summary = summarize_service_points(service)
    profile = packages.merge(service_summary, on="kommun", how="outer", validate="1:1")
    profile = add_indicators(profile)
    profile = profile.sort_values("preliminar_screeningrank")

    out_csv = DERIVED / "kommun_paket_service_screening.csv"
    profile.to_csv(out_csv, index=False, encoding="utf-8-sig")
    write_markdown_profile(profile)
    print(f"Wrote {out_csv}")
    print(f"Wrote {DOCS / 'forsta_dataprofil.md'}")


if __name__ == "__main__":
    main()
