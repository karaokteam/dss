"""Streamlit demo. Sekmeler ui/ altında; bu dosya sadece bağlar.

streamlit run app.py
"""

import streamlit as st

from ui import tab_chat, tab_evaluate, tab_status

st.set_page_config(page_title="Üs Koruma Agent'ı", layout="wide")
st.title("Üs Koruma Agent'ı")

for tab, page in zip(
    st.tabs(["Değerlendir", "Durum tablosu", "Sohbet"]), [tab_evaluate, tab_status, tab_chat], strict=True
):
    with tab:
        page.render()
