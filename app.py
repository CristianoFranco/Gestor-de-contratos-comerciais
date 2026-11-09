import streamlit as st
import os
import pandas as pd
from supabase import create_client

# Configuração da página
st.set_page_config(
    page_title="Globex Multimodal - Gestão de Contratos & Faturamentos",
    page_icon="📦",
    layout="wide"
)

# Conexão Supabase
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None

supabase = init_supabase()

def get_base64_of_bin_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            import base64
            return base64.b64encode(f.read()).decode()
    return ""

# Estilização visual limpa e profissional
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0c3547 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .portal-card {
        background-color: white;
        padding: 30px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        text-align: center;
        border-top: 5px solid #0c3547;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# Gestão de estados de navegação entre portais
if "modulo_ativo" not in st.session_state:
    st.session_state["modulo_ativo"] = "home"

def voltar_ao_inicio():
    st.session_state["modulo_ativo"] = "home"
    st.rerun()

# -------------------------------------------------------------------------
# TELA INICIAL / PORTAL CORPORATIVO
# -------------------------------------------------------------------------
if st.session_state["modulo_ativo"] == "home":
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #0c3547;'>Portal Corporativo - Globex Multimodal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666; font-size: 16px;'>Selecione abaixo o sistema que deseja aceder:</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("""
            <div class="portal-card">
                <h3>📦 Gestor de Contratos</h3>
                <p style="color: #666;">Controlo de vigências, reajustes, alertas automáticos e gestão de clientes.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Aceder a Contratos", use_container_width=True, key="btn_portal_contratos"):
            st.session_state["modulo_ativo"] = "contratos"
            st.rerun()

    with col2:
        st.markdown("""
            <div class="portal-card">
                <h3>💰 Gestor de Faturamentos</h3>
                <p style="color: #666;">Módulo dedicado à gestão automática de faturamentos e prazos operacionais.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Aceder a Faturamentos", use_container_width=True, key="btn_portal_faturamentos"):
            st.session_state["modulo_ativo"] = "faturamentos"
            st.rerun()

    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888; font-size: 13px;'>© 2026 Globex Multimodal</p>", unsafe_allow_html=True)

# -------------------------------------------------------------------------
# MÓDULO 1: GESTÃO DE CONTRATOS
# -------------------------------------------------------------------------
elif st.session_state["modulo_ativo"] == "contratos":
    if st.button("⬅️ Voltar ao Início", key="voltar_inicio_contratos"):
        voltar_ao_inicio()
    
    st.markdown("---")
    
    try:
        import contratos
        contratos.executar()
    except Exception as e:
        st.error(f"Erro ao carregar o módulo de contratos: {e}")

# -------------------------------------------------------------------------
# MÓDULO 2: GESTÃO DE FATURAMENTOS
# -------------------------------------------------------------------------
elif st.session_state["modulo_ativo"] == "faturamentos":
    if st.button("⬅️ Voltar ao Início", key="voltar_inicio_faturamentos"):
        voltar_ao_inicio()
    
    st.markdown("---")
    
    try:
        import faturamentos
        faturamentos.executar()
    except Exception as e:
        st.error(f"Erro ao carregar o módulo de faturamentos: {e}")
