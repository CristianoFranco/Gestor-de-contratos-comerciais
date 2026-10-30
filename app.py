import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import calendar
from supabase import create_client, Client

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E DESIGN CUSTOMIZADO
# ==========================================
st.set_page_config(
    page_title="Gestor de Contratos - Globex Multimodal",
    page_icon="📦",
    layout="wide"
)

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0c3547 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stButton>button { background-color: #0c3547; color: white; border-radius: 8px; border: none; padding: 0.5rem 1rem; font-weight: 600; transition: 0.3s; }
    .stButton>button:hover { background-color: #00b4d8; color: #0c3547; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 5px solid #00b4d8; text-align: center; }
    .metric-card-alert { border-left: 5px solid #d90429; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONEXÃO COM O SUPABASE
# ==========================================
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase. Verifique se os Secrets foram configurados corretamente: {e}")
        return None

supabase = init_supabase()

# ==========================================
# CARREGAR CONFIGURAÇÕES DE E-MAIL DO SUPABASE
# ==========================================
def carregar_config_email():
    if not supabase:
        return {}
    try:
        res = supabase.table("config_email").select("*").eq("id", 1).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {}

config_db = carregar_config_email()

if "provedor" not in st.session_state:
    st.session_state["provedor"] = config_db.get("provedor", "Outlook / Office365")
if "email_remetente" not in st.session_state:
    st.session_state["email_remetente"] = config_db.get("email_remetente", "")
if "senha_remetente" not in st.session_state:
    st.session_state["senha_remetente"] = config_db.get("senha_remetente", "")
if "email_comercial_globex" not in st.session_state:
    st.session_state["email_comercial_globex"] = config_db.get("email_comercial_globex", "")

# ==========================================
# FUNÇÕES DE E-MAIL
# ==========================================
def enviar_email(provedor, email_remetente, senha, email_destino, assunto, mensagem):
    try:
        if provedor == "Gmail":
            smtp_server = "smtp.gmail.com"
            port = 587
        elif provedor == "Outlook / Office365":
            smtp_server = "smtp.office365.com"
            port = 587
        else:
            return False, "Provedor inválido."

        msg = MIMEMultipart()
        msg['From'] = email_remetente
        msg['To'] = email_destino
        msg['Subject'] = assunto
        msg.attach(MIMEText(mensagem, 'plain'))

        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(email_remetente, senha)
        server.send_message(msg)
        server.quit()
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, str(e)

def executar_automacao_alertas():
    remetente = st.session_state.get("email_remetente") or config_db.get("email_
