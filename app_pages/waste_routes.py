"""Independent map of DVA collection places and tract layers."""
import streamlit as st
from waste_review import asset_signature, embedded_map_html


@st.cache_data(show_spinner=False, max_entries=2)
def load_map_html(signature):
    return embedded_map_html()


st.caption(
    'DVA:s sophämtningsschema 2026 med fler namngivna orter och gator. '
    'Tänd/släck kommuner och trakter i Gagnef, Leksand, Rättvik och Vansbro.'
)
st.info(
    'Sophämtningsplatserna anger namngivna orter och gator ur schemat. '
    'De är inte hämtställen eller körvägar. Grå reserver ligger vid traktankare '
    'och orange markeringar anger träffar att granska.'
)
st.page_link('app_pages/comparison.py',label='Öppna Sophämtning + transporter + service',icon=':material/layers:')
try:
    signature=asset_signature()
except FileNotFoundError:
    st.error('Kartunderlag saknas. Bygg DVA:s platslager enligt prototypes/dva_transportnarvaro/README.md.')
    st.stop()

st.iframe(load_map_html(signature), height=1150, width='stretch')
