import streamlit as st
import os

def executar():
    with st.sidebar:
        caminho_logo_side = "Logo.png" if os.path.exists("Logo.png") else ("logo.png" if os.path.exists("logo.png") else None)
        if caminho_logo_side:
            st.image(caminho_logo_side, use_container_width=True)
        else:
            st.markdown("### 🌐 GLOBEX MULTIMODAL")
        
        st.markdown("---")
        menu = ["Visão Geral / Dashboard", "Lançamentos de Faturamento", "Relatórios"]
        opcao = st.radio("Navegação Faturamentos", menu)
        st.markdown("---")
        st.caption("© 2026 Globex Multimodal")

    st.markdown("<h1 style='text-align: center; color: #0c3547;'>💰 Gestor de Faturamentos</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Módulo em desenvolvimento para acompanhamento financeiro de faturas.</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    st.info(f"📍 Funcionalidade selecionada: **{opcao}**. Este módulo está pronto para começarmos a criar as tabelas e rotinas específicas de faturamento!")
