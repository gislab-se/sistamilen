"""Interaktiv screeningkarta för DVA:s sophämtning."""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAP_ROOT = PROJECT_ROOT / "prototypes" / "dva_transportnarvaro"


@st.cache_data(show_spinner=False)
def load_map_html() -> str:
    """Läs prototypen och bädda in lokala Leaflet-resurser för publicering."""
    html = (MAP_ROOT / "index.html").read_text(encoding="utf-8")
    leaflet_css = (MAP_ROOT / "vendor" / "leaflet.css").read_text(encoding="utf-8")
    leaflet_js = (MAP_ROOT / "vendor" / "leaflet.js").read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="vendor/leaflet.css">',
        f"<style>\n{leaflet_css}\n</style>",
    )
    html = html.replace(
        '<script src="vendor/leaflet.js"></script>',
        f"<script>\n{leaflet_js}\n</script>",
    )
    return html


st.caption(
    "DVA:s publicerade sophämtningsschema 2026 jämfört med observerade "
    "paketservicenoder i Gagnef, Leksand, Rättvik och Vansbro."
)
st.warning(
    "Detta är en screeningkarta: markörerna är geokodade ankarorter för "
    "trakter, inte faktiska körvägar, stoppordning eller hämtningsställen."
)

components.html(load_map_html(), height=900, scrolling=False)
