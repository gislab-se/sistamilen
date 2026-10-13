"""Observed trip presence and calculated road routes, for local review."""
import streamlit as st

from transport_review import asset_signature, embedded_map_html


@st.cache_data(show_spinner=False, max_entries=2)
def load_transport_map(signature):
    return embedded_map_html()


st.caption(
    'Observerade detaljresor 21–27 september 2026. Tänd och släck namngivna '
    'fordonslager för att jämföra den geografiska transportnärvaron.'
)
st.info(
    'Namn beskriver besöksorter, inte bekräftad verksamhet. NVDB-rutterna är '
    'beräknade vägförslag från adress-/reservpunkter. Underlaget visar inte '
    'ledig lastkapacitet eller att paket har transporterats.'
)
with st.container(horizontal=True):
    st.page_link('app_pages/comparison.py', label='Sophämtning + transporter + service', icon=':material/layers:')
    st.page_link('app_pages/simulation.py', label='Jämför med tillgänglighet och bortfall', icon=':material/science:')

try:
    signature = asset_signature()
except FileNotFoundError:
    st.error('Granskningskartans lokala filer saknas. Bygg underlaget enligt prototypes/fredriksberg_resor/README.md.')
    st.stop()

st.iframe(load_transport_map(signature), height=1100, width='stretch')

with st.expander('Hur transportanalysen kan komplettera bortfallsanalysen'):
    st.markdown(
        '1. Jämför beräknade transportkorridorer med paketservicenoder och DVA:s '
        'schemalagda närvaro på orter. Skilj passager från registrerade besök.\n'
        '2. Vid ett hypotetiskt nodbortfall: undersök om berörda orter har '
        'observerad transportnärvaro och vilka alternativa noder som kan nås.\n'
        '3. Pröva samordning som ett separat scenario med tider, möjlig omväg '
        'och bekräftad kapacitet. Befolknings- och tillgänglighetsmåtten behåller '
        'sina ursprungliga definitioner.\n\n'
        'Den gemensamma jämförelsen finns på fliken Sophämtning + transporter + service; ort-/datumöverlapp '
        'visar var publicerad hämtning och registrerade besök sammanfaller. '
        'Den räknar ännu inte ut samordningspotential eller ändrar bortfallsresultaten.'
    )
