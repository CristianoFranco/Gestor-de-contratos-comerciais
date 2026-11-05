import streamlit as st
import os

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Portal Globex Multimodal",
    page_icon="📦",
    layout="wide"
)

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0c3547 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stButton>button { background-color: #0c3547; color: white; border-radius: 8px; border: none; padding: 0.75rem 1.5rem; font-weight: 600; font-size: 16px; transition: 0.3s; width: 100%; }
    .stButton>button:hover { background-color: #00b4d8; color: #0c3547; }
    .card-home { background-color: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center; border-top: 5px solid #0c3547; }
    </style>
""", unsafe_allow_html=True)

# Inicializa o estado de navegação
if "modulo_ativo" not in st.session_state:
    st.session_state["modulo_ativo"] = "home"

# ==========================================
# TELA DE INÍCIO (HOME)
# ==========================================
if st.session_state["modulo_ativo"] == "home":
    caminho_logo = "Logo.png" if os.path.exists("Logo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if caminho_logo:
        col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
        with col_l2:
            st.image(caminho_logo, use_container_width=True)

    st.markdown("<h1 style='text-align: center; color: #0c3547; margin-top: 20px;'>Portal Corporativo - Globex Multimodal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666; font-size: 18px;'>Selecione abaixo o sistema que deseja aceder:</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([1, 2, 2, 1], gap="medium")
    
    with col2:
        st.markdown("""
            <div class="card-home">
                <h3>📦 Gestor de Contratos</h3>
                <p style="color: #666; min-height: 50px;">Controlo de vigências, reajustes, alertas automáticos e gestão de clientes.</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Aceder a Contratos", key="btn_contratos"):
            st.session_state["modulo_ativo"] = "contratos"
            st.rerun()

    with col3:
        st.markdown("""
            <div class="card-home" style="border-top-color: #00b4d8;">
                <h3>💰 Gestor de Faturamentos</h3>
                <p style="color: #666; min-height: 50px;">Módulo dedicado à gestão automática de faturamentos.</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Aceder a Faturamentos", key="btn_faturamentos"):
            st.session_state["modulo_ativo"] = "faturamentos"
            st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888;'>© 2026 Globex Multimodal</p>", unsafe_allow_html=True)

# ==========================================
# ROTEAMENTO PARA OS MÓDULOS
# ==========================================
elif st.session_state["modulo_ativo"] == "contratos":
    if st.button("⬅️ Voltar ao Início", key="voltar_home_c"):
        st.session_state["modulo_ativo"] = "home"
        st.rerun()
    st.divider()
    
    import contratos
    contratos.executar()

elif st.session_state["modulo_ativo"] == "faturamentos":
    if st.button("⬅️ Voltar ao Início", key="voltar_home_f"):
        st.session_state["modulo_ativo"] = "home"
        st.rerun()
    st.divider()
    
    import faturamentos
    faturamentos.executar()
