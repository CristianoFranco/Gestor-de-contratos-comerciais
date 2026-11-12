import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import calendar

def carregar_config_email(supabase):
    try:
        res = supabase.table("config_email").select("*").eq("id", 1).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {}

def enviar_email(provedor, email_remetente, senha, destino, assunto, mensagem):
    try:
        if provedor == "Gmail":
            smtp_server = "smtp.gmail.com"
            port = 587
        elif provedor == "Outlook / Office365":
            smtp_server = "smtp.office365.com"
            port = 587
        else:
            return False, "Provedor inválido."

        server = smtplib.SMTP(smtp_server, port, timeout=10)
        server.starttls()
        server.login(email_remetente, senha)

        msg = MIMEMultipart()
        msg['From'] = email_remetente
        msg['To'] = destino
        msg['Subject'] = assunto
        msg.attach(MIMEText(mensagem, 'plain'))
        server.send_message(msg)
        server.quit()
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, str(e)

def executar():
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

    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase = create_client(url, key)
    except Exception as e:
        st.error(f"Erro crítico ao conectar ao Supabase: {e}")
        return

    config_db = carregar_config_email(supabase)

    if "provedor" not in st.session_state:
        st.session_state["provedor"] = config_db.get("provedor", "Outlook / Office365")
    if "email_remetente" not in st.session_state:
        st.session_state["email_remetente"] = config_db.get("email_remetente", "")
    if "senha_remetente" not in st.session_state:
        st.session_state["senha_remetente"] = config_db.get("senha_remetente", "")
    if "email_comercial_globex" not in st.session_state:
        st.session_state["email_comercial_globex"] = config_db.get("email_comercial_globex", "")

    with st.sidebar:
        caminho_logo_side = "Logo.png" if os.path.exists("Logo.png") else ("logo.png" if os.path.exists("logo.png") else None)
        if caminho_logo_side:
            st.image(caminho_logo_side, use_container_width=True)
        else:
            st.markdown("### 🌐 GLOBEX MULTIMODAL")
        
        st.markdown("---")
        menu = ["Cadastro de Contrato", "Gestão de Contratos", "Configurações de E-mail"]
        opcao = st.radio("Navegação Contratos", menu)
        st.markdown("---")
        st.caption("© 2026 Globex Multimodal")

    if opcao == "Cadastro de Contrato":
        st.markdown("<h1 style='text-align: center; color: #0c3547;'>📋 Gestão de Contratos Globex</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Cadastre novos contratos ou gerencie os registos existentes.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        aba_novo, aba_editar = st.tabs(["➕ Novo Contrato", "✏️ Editar / Excluir Contrato"])

        with aba_novo:
            st.subheader("Novo Contrato")

            col1, col2 = st.columns(2)
            with col1:
                nome_cliente = st.text_input("Nome do Cliente *", key="input_novo_cliente")
                num
