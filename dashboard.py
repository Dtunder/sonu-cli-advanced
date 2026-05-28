import streamlit as st
import pandas as pd
import sqlite3
import os
import sys

# Pfad zu Sonu-CLI Advanced
sys.path.append(os.path.abspath("../"))
from agents_swarm.orchestrator import SwarmOrchestrator

st.set_page_config(page_title="Sonu Swarm Dashboard", layout="wide")
st.title("Sonu-CLI: Swarm Intelligence & Strategy Dashboard")

orchestrator = SwarmOrchestrator()
db_path = os.path.join(os.path.dirname(__file__), "skills", "sonu.db")

# Tabs für Swarm-Interaktion und Analyse
tab1, tab2 = st.tabs(["Agent Swarm", "Strategie-Analyse"])

with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        task = st.text_area("Aufgabe eingeben:", "Analysiere Orderbook für Arbitrage...")
        role = st.selectbox("Rolle wählen:", ["regelung", "hft", "rl", "architektur", "code"])
        if st.button("Agent Swarm triggern"):
            with st.spinner("Agenten debattieren & recherchieren..."):
                st.session_state.result = orchestrator.route_task(task, role)
    with col2:
        st.subheader("Agent Output")
        st.write(st.session_state.get("result", "Warte auf Task..."))

with tab2:
    st.subheader("Strategie-Entscheidungen (Log-Analyse)")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM swarm_logs", conn)
        conn.close()
        
        if not df.empty:
            st.bar_chart(df['role'].value_counts())
            st.dataframe(df)
        else:
            st.write("Noch keine Daten geloggt.")
    else:
        st.error("Datenbank nicht gefunden.")
