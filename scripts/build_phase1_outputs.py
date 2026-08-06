"""Bygg reproducerbara Fas 1-tabeller från projektets källdata."""

from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard_data import build_service_nodes, load_dashboard_data  # noqa: E402


DERIVED = ROOT / "data" / "derived"
WORKING = ROOT / "data" / "working"


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Skrev {path.relative_to(ROOT)} ({len(frame)} rader)")


def stable_key(value: str) -> str:
    """Skapa en läsbar nyckeldel som inte beror på tabellens radordning."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]+", "-", ascii_value.upper()).strip("-")


def seed_change_register() -> pd.DataFrame:
    """Skapa startposter med separata fall-, händelse- och evidensnycklar.

    Posterna är verifieringskandidater. De beskriver inte en fastställd
    stängning eller ansvarig aktör.
    """
    columns = [
        "registerpost_id",
        "fall_id",
        "plats_id",
        "plats",
        "kommun",
        "kluster_id",
        "uuidadrpl",
        "geografisk_matchstatus",
        "handelse_id",
        "handelsekategori",
        "handelsebeskrivning",
        "handelsestatus",
        "handelsedatum",
        "datumprecision",
        "aktor",
        "aktorstatus",
        "tidigare_service",
        "observerat_nulage",
        "ersattning",
        "orsak",
        "konsekvens",
        "evidens_id",
        "evidenstyp",
        "kallreferens",
        "kallurl",
        "kallstatus",
        "evidensstyrka",
        "verifieringsstatus",
        "senast_kontrollerad",
        "nasta_kontroll",
        "anteckning",
    ]
    records = [
        {
            "registerpost_id": "RP001",
            "fall_id": "F001",
            "plats_id": "PL-BINGSJO",
            "plats": "Bingsjö",
            "kommun": "Rättvik",
            "kluster_id": 7914,
            "uuidadrpl": "e1bccca6-dc40-47a5-b18d-13a4264edf85",
            "geografisk_matchstatus": "Exakt match mot adresskluster 2026",
            "handelse_id": "H-KAND-001",
            "handelsekategori": "Uppgift om möjlig serviceförändring",
            "handelsebeskrivning": (
                "Bingsjö anges som påverkad plats i uppdragsbeskrivningen"
            ),
            "handelsestatus": "Kandidat – händelse ej verifierad",
            "handelsedatum": "",
            "datumprecision": "Okänd",
            "aktor": "",
            "aktorstatus": "Aktör för möjlig förändring ej fastställd",
            "tidigare_service": "Ej fastställd",
            "observerat_nulage": (
                "TVV-stödbutik finns i servicepunktsdata 2026; "
                "leveransfrekvens saknas"
            ),
            "ersattning": "Ej fastställd",
            "orsak": "Ej fastställd",
            "konsekvens": "Ej fastställd",
            "evidens_id": "E001",
            "evidenstyp": "Dokumentuppgift + nulägesobservation",
            "kallreferens": (
                "Uppdragsbeskrivning 2026-03-26; "
                "Servicepunkter_2026_Dalarna.xlsx, sp2026"
            ),
            "kallurl": "",
            "kallstatus": (
                "Platsomnämnande och nulägesrad finns; "
                "förändringshändelsen saknar primärkälla"
            ),
            "evidensstyrka": "Indikation",
            "verifieringsstatus": "Behöver verifieras",
            "senast_kontrollerad": "2026-08-05",
            "nasta_kontroll": (
                "Bekräfta tidigare/nuvarande paketservice, aktör, "
                "datum, orsak och alternativ"
            ),
            "anteckning": "Förekomst av butik bevisar inte paketservice.",
        },
        {
            "registerpost_id": "RP002",
            "fall_id": "F002",
            "plats_id": "PL-BY-AVESTA",
            "plats": "By",
            "kommun": "Avesta",
            "kluster_id": "",
            "uuidadrpl": "",
            "geografisk_matchstatus": "Ingen exakt textmatch i 2026-data",
            "handelse_id": "H-KAND-002",
            "handelsekategori": "Uppgift om möjlig serviceförändring",
            "handelsebeskrivning": (
                "By anges som påverkad plats i uppdragsbeskrivningen"
            ),
            "handelsestatus": "Kandidat – händelse ej verifierad",
            "handelsedatum": "",
            "datumprecision": "Okänd",
            "aktor": "",
            "aktorstatus": "Aktör för möjlig förändring ej fastställd",
            "tidigare_service": "Ej fastställd",
            "observerat_nulage": (
                "Ingen exakt platsmatch i servicepunktsdata 2026"
            ),
            "ersattning": "Ej fastställd",
            "orsak": "Ej fastställd",
            "konsekvens": "Ej fastställd",
            "evidens_id": "E002",
            "evidenstyp": "Dokumentuppgift + negativ textmatch",
            "kallreferens": (
                "Uppdragsbeskrivning 2026-03-26; "
                "Servicepunkter_2026_Dalarna.xlsx, sp2026 och Kluster"
            ),
            "kallurl": "",
            "kallstatus": (
                "Platsomnämnande finns; geografi och förändringshändelse "
                "saknar primärkälla"
            ),
            "evidensstyrka": "Indikation",
            "verifieringsstatus": "Behöver verifieras",
            "senast_kontrollerad": "2026-08-05",
            "nasta_kontroll": (
                "Verifiera geografisk avgränsning, tidigare service, aktör, "
                "datum, orsak och alternativ"
            ),
            "anteckning": "Frånvaro i filen bevisar inte servicebortfall.",
        },
    ]
    return pd.DataFrame(records, columns=columns)


def build_actor_matrix(service: pd.DataFrame) -> pd.DataFrame:
    """Skapa en kandidatmatris utan att tillskriva verifierat ansvar."""
    commercial = (
        service.groupby("aktor", as_index=False)
        .agg(
            rader_i_kalldata=("DB_ID_2026", "count"),
            fysiska_noder=("kluster_id", "nunique"),
            observerade_tjanster=(
                "typ_servicepunkt",
                lambda x: "; ".join(sorted(set(x.dropna()))),
            ),
        )
        .sort_values("aktor")
        .reset_index(drop=True)
    )
    commercial.insert(
        0,
        "aktor_id",
        commercial["aktor"].map(lambda value: f"A-PKT-{stable_key(value)}"),
    )
    if not commercial["aktor_id"].is_unique:
        raise ValueError("Aktörsnamnen gav kolliderande aktörsnycklar.")
    commercial["kandidatstatus"] = (
        "Observerad i källdata; kandidat till datadialog"
    )
    commercial["aktorstyp"] = "Paket-/serviceaktör i källdata"
    commercial["geografisk_niva"] = "Nod, kommun och län"
    commercial["radighetsniva"] = "Potentiellt direkt operativ"
    commercial["radighetsstatus"] = (
        "Kandidat – behöver verifieras per aktör och plats"
    )
    commercial["mojlig_roll_i_fas1"] = (
        "Verifiera nät, förändringar, volymer, leveransfrekvens och beslutskriterier"
    )
    commercial["formellt_ansvar"] = (
        "Ej kartlagt; förekomst i källdata visar inte formellt ansvar"
    )
    commercial["kallreferens"] = (
        "Servicepunkter_2026_Dalarna.xlsx, blad sp2026"
    )
    commercial["kallstatus"] = (
        "Aktörsförekomst och tjänster belagda; mandat och ansvar ej verifierade"
    )
    commercial["kontaktstatus"] = "Ej kontaktad"
    commercial["databehov"] = (
        "Historik per plats; hotade noder; faktisk volym eller zon; kontaktperson"
    )
    commercial["nasta_steg"] = (
        "Verifiera kontaktperson, mandat, datadelning och vilka beslut aktören kan påverka"
    )

    candidates = pd.DataFrame(
        [
            {
                "aktor_id": "A-KAND-001",
                "aktor": "Region Dalarna",
                "aktorstyp": "Regional offentlig aktör",
                "geografisk_niva": "Län",
                "radighetsniva": "Potentiellt regionalt strategisk och samordnande",
                "mojlig_roll_i_fas1": "RUS, regional analys, kommersiell service och samordning",
                "databehov": "Ansvarig funktion; regionala underlag; beslut och program",
                "kallreferens": "Uppdragsbeskrivning 2026-03-26",
                "kallstatus": (
                    "Beställarroll belagd; specifikt mandat och operativ rådighet ej verifierade"
                ),
                "nasta_steg": "Bekräfta ansvarig funktion, mandat och beslutspunkter",
            },
            {
                "aktor_id": "A-KAND-002",
                "aktor": "Dalarnas kommuner",
                "aktorstyp": "Lokala offentliga aktörer",
                "geografisk_niva": "Kommun och lokal plats",
                "radighetsniva": "Potentiellt lokalt samordnande och beställande",
                "mojlig_roll_i_fas1": "Verifiera lokala händelser, konsekvenser och servicebehov",
                "databehov": "Kontaktperson; händelsehistorik; lokala planer och fall",
                "kallreferens": "Uppstart 2026-07-03; databehovsrapport",
                "kallstatus": (
                    "Aktörsgrupp omnämnd; mandat och ansvar behöver verifieras per kommun"
                ),
                "nasta_steg": "Identifiera kontakt och rådighet i varje berörd kommun",
            },
            {
                "aktor_id": "A-KAND-003",
                "aktor": "Post- och telestyrelsen (PTS)",
                "aktorstyp": "Statlig myndighet",
                "geografisk_niva": "Nationell och regional data",
                "radighetsniva": "Potentiellt regel-, tillsyns- och kunskapsstöd",
                "mojlig_roll_i_fas1": "Nationella marknadsunderlag, tillsyn och geografiska klagomålsdata",
                "databehov": "Tillgängliga geografiska data; rapporter; kontaktväg",
                "kallreferens": "Uppstart 2026-07-03; databehovsrapport",
                "kallstatus": "Databehov omnämnt; roll i projektet ej verifierad",
                "nasta_steg": "Verifiera tillgängliga data, kontaktväg och avgränsning",
            },
            {
                "aktor_id": "A-KAND-004",
                "aktor": "Dalatrafik",
                "aktorstyp": "Regional kollektivtrafikaktör",
                "geografisk_niva": "Län, stråk och hållplats",
                "radighetsniva": "Potentiellt operativt och samordnande transportflöde",
                "mojlig_roll_i_fas1": "Underlag om linjer, hållplatser, depåer och vändpunkter",
                "databehov": "Linjenät; turtäthet; depåer; möjliga samordningsbegränsningar",
                "kallreferens": "Uppstart 2026-07-03; databehovsrapport",
                "kallstatus": "Samordningskandidat omnämnd; faktisk rådighet ej verifierad",
                "nasta_steg": "Verifiera dataägare, kontakt och realistiska samordningsytor",
            },
            {
                "aktor_id": "A-KAND-005",
                "aktor": "Servicepunktsvärdar och lokala handlare",
                "aktorstyp": "Lokala operativa kandidater",
                "geografisk_niva": "Adress-/servicenod och lokalt omland",
                "radighetsniva": "Potentiellt lokalt operativ",
                "mojlig_roll_i_fas1": "Verifiera nodens funktion, kapacitet, villkor och lokal betydelse",
                "databehov": "Kontakt; avtalspart; kapacitet; öppettider; historik; lokala konsekvenser",
                "kallreferens": "Servicepunkter 2026; databehovsrapport",
                "kallstatus": "Lokala noder observerade; respektive värds mandat ej verifierat",
                "nasta_steg": "Identifiera och intervjua värdar i prioriterade platsfall",
            },
            {
                "aktor_id": "A-KAND-006",
                "aktor": "Berörda kommunala transportverksamheter",
                "aktorstyp": "Kommunala flödesaktörer",
                "geografisk_niva": "Kommun, rutt och lokalt upptagningsområde",
                "radighetsniva": "Potentiellt beställande eller operativt transportflöde",
                "mojlig_roll_i_fas1": "Pröva samband med hemtjänst, matdistribution och skolskjuts",
                "databehov": "Aggregerade rutter; volymer; tidfönster; sekretess- och verksamhetskrav",
                "kallreferens": "Uppstart 2026-07-03; databehovsrapport",
                "kallstatus": "Flöden omnämnda; ansvariga enheter och rådighet ej identifierade",
                "nasta_steg": "Avgränsa verksamheter och verifiera data- och samordningsmöjlighet",
            },
            {
                "aktor_id": "A-KAND-007",
                "aktor": "Maserfrakt och andra fraktaktörer",
                "aktorstyp": "Kommersiella logistikaktörer",
                "geografisk_niva": "Terminal, stråk och distributionsområde",
                "radighetsniva": "Potentiellt direkt operativt logistikflöde",
                "mojlig_roll_i_fas1": "Underlag om terminaler, huvudstråk och distributionsmönster",
                "databehov": "Kontakt; terminaler; stråk; kapacitet; kommersiella begränsningar",
                "kallreferens": "Uppstart 2026-07-03; databehovsrapport",
                "kallstatus": "Samordningskandidat omnämnd; deltagande och rådighet ej verifierade",
                "nasta_steg": "Verifiera relevanta bolag, kontakt och möjligt dataunderlag",
            },
            {
                "aktor_id": "A-KAND-008",
                "aktor": "Fredriksbergstvätten",
                "aktorstyp": "Tvätt- och distributionsflöde",
                "geografisk_niva": "Rutt och distributionsområde",
                "radighetsniva": "Potentiellt operativt samordningsflöde",
                "mojlig_roll_i_fas1": "Pröva geografisk och tidsmässig samordning med paketflöden",
                "databehov": "Dataägare; rutter; volymer; tidfönster; kapacitets- och avtalsvillkor",
                "kallreferens": "Uppstart 2026-07-03; databehovsrapport",
                "kallstatus": "Samordningskandidat omnämnd; organisation och rådighet ej verifierade",
                "nasta_steg": "Verifiera juridisk aktör, kontakt, data och samordningsbarhet",
            },
            {
                "aktor_id": "A-KAND-009",
                "aktor": "Boende och lokala företag",
                "aktorstyp": "Behovs- och kunskapsaktörer",
                "geografisk_niva": "Plats och lokalt omland",
                "radighetsniva": "Behovs- och kunskapsinflytande, inte antagen beslutanderådighet",
                "mojlig_roll_i_fas1": "Beskriva konsekvenser, acceptabel tillgänglighet och lokala värden",
                "databehov": "Intervjuer; resmönster; företagsbehov; social funktion; säsongsvariation",
                "kallreferens": "Databehovsrapport",
                "kallstatus": "Intervjugrupp omnämnd; representation och urval ej fastställda",
                "nasta_steg": "Ta fram transparent urval och intervjuguide för prioriterade platsfall",
            },
        ]
    )
    candidates["kandidatstatus"] = (
        "Omnämnd i projektunderlag; kandidat till verifiering"
    )
    candidates["radighetsstatus"] = "Ej verifierad i projektet"
    candidates["rader_i_kalldata"] = 0
    candidates["fysiska_noder"] = 0
    candidates["observerade_tjanster"] = ""
    candidates["formellt_ansvar"] = (
        "Ej fastställt; kandidatrollen visar inte formellt ansvar"
    )
    candidates["kontaktstatus"] = "Ej kontaktad"

    columns = [
        "aktor_id",
        "aktor",
        "kandidatstatus",
        "aktorstyp",
        "geografisk_niva",
        "radighetsniva",
        "radighetsstatus",
        "rader_i_kalldata",
        "fysiska_noder",
        "observerade_tjanster",
        "mojlig_roll_i_fas1",
        "formellt_ansvar",
        "kallreferens",
        "kallstatus",
        "kontaktstatus",
        "databehov",
        "nasta_steg",
    ]
    return pd.concat([commercial, candidates], ignore_index=True)[columns]


def seed_place_cases(service: pd.DataFrame) -> pd.DataFrame:
    bingsjo = service.loc[
        service.astype(str)
        .apply(lambda column: column.str.contains("Bingsjö", case=False, na=False))
        .any(axis=1)
    ]
    bingsjo_row = bingsjo.iloc[0] if not bingsjo.empty else pd.Series(dtype=object)
    return pd.DataFrame(
        [
            {
                "plats": "Bingsjö",
                "kommun": "Rättvik",
                "prioritet": 1,
                "status": "Nulägesrad finns; förändring behöver verifieras",
                "lon": bingsjo_row.get("lon", pd.NA),
                "lat": bingsjo_row.get("lat", pd.NA),
                "kopplad_nod": bingsjo_row.get("kluster_id", pd.NA),
                "fragor": "Tidigare service? Aktör? Datum? Alternativ? Lokal betydelse?",
            },
            {
                "plats": "By",
                "kommun": "Avesta",
                "prioritet": 1,
                "status": "Ingen exakt match; geografi och förändring behöver verifieras",
                "lon": pd.NA,
                "lat": pd.NA,
                "kopplad_nod": pd.NA,
                "fragor": "Vilket By? Tidigare service? Datum? Närmaste alternativ? Konsekvenser?",
            },
        ]
    )


def write_if_missing(frame: pd.DataFrame, path: Path) -> None:
    if path.exists():
        print(f"Bevarade befintligt arbetsunderlag {path.relative_to(ROOT)}")
        return
    write_csv(frame, path)


def main() -> None:
    _, service, profile, clusters, _ = load_dashboard_data(ROOT)
    nodes = build_service_nodes(service, clusters)
    write_csv(nodes, DERIVED / "servicenoder_2026.csv")
    write_csv(profile, DERIVED / "kommun_screening_fas1.csv")
    write_if_missing(seed_change_register(), WORKING / "forandringsregister.csv")
    write_if_missing(build_actor_matrix(service), WORKING / "aktorsmatris.csv")
    write_if_missing(seed_place_cases(service), WORKING / "platsfall.csv")


if __name__ == "__main__":
    main()
