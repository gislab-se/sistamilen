"""Combined review of collection places, observed trips and parcel service."""
import streamlit as st

from transport_review import asset_signature, embedded_map_html


@st.cache_data(show_spinner=False,max_entries=2)
def load_map_html(signature):
    return embedded_map_html(context='combined')


st.caption('Sophämtningsplatser, namngivna fordonsrutter och paketservicenoder i samma karta. Tänd/släck lager och jämför med gemensamt datum- och kommunfilter.')
st.info('Ort-/datumträffar jämför publicerad sophämtning med registrerade start/stoppadresser under 21–27 september 2026. De visar inte samtidighet eller bekräftad samordningskapacitet.')
with st.container(horizontal=True):
    st.page_link('app_pages/waste_routes.py',label='Egen sophämtningskarta',icon=':material/recycling:')
    st.page_link('app_pages/transports.py',label='Egen transportanalys',icon=':material/route:')

try:
    signature=asset_signature()
except FileNotFoundError:
    st.error('Kartunderlag saknas. Bygg plats- och transportunderlagen enligt metodbeskrivningarna.')
    st.stop()

st.iframe(load_map_html(signature),height=1150,width='stretch')
