import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import calendar

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E DESIGN CUSTOMIZADO
# ==========================================
st.set_page_config(
    page_title="Gestor de Contratos - Globex Multimodal",
    page_icon="📦",
    layout="wide"
)

# Cores extraídas do Logotipo da Globex:
# Azul Escuro/Petróleo: #0c3547 | Azul Ciano: #00b4d8 | Vermelho: #d90429 | Cinza Claro Fundo: #f8f9fa
st.markdown("""
    <style>
    .stApp {
        background-color: #f8f9fa;
    }
    h1, h2, h3 {
        color: #0c3547 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stButton>button {
        background-color: #0c3547;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #00b4d8;
        color: #0c3547;
    }
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #00b4d8;
        text-align: center;
    }
    .metric-card-alert {
        border-left: 5px solid #d90429;
    }
    </style>
""", unsafe_allow_html=True)

def init_db():
    conn = sqlite3.connect("contratos.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            num_contrato TEXT UNIQUE NOT NULL,
            data_inicio DATE NOT NULL,
            vigencia_meses INTEGER NOT NULL,
            data_fim DATE NOT NULL,
            email_cliente TEXT NOT NULL,
            telefone_cliente TEXT NOT NULL,
            status TEXT NOT NULL,
            alerta_45_enviado INTEGER DEFAULT 0,
            alerta_30_enviado INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

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
            return False, "Provedor não suportado."

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
    if "email_remetente" not in st.session_state or not st.session_state["email_remetente"]:
        return "Configure as credenciais de correio eletrónico na aba 'Configurações de E-mail' para ativar a automação."

    conn = sqlite3.connect("contratos.db")
    c = conn.cursor()
    c.execute("SELECT id, cliente, num_contrato, data_fim, email_cliente, alerta_45_enviado, alerta_30_enviado, status FROM contratos")
    contratos = c.fetchall()

    hoje = datetime.now().date()
    disparos_45 = 0
    disparos_30 = 0

    for item in contratos:
        cid, cliente, num_contrato, data_fim_str, email_cliente, a45, a30, status_atual = item
        data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
        dias_restantes = (data_fim - hoje).days

        # 45 dias -> Comercial Globex
        if dias_restantes <= 45 and dias_restantes > 30 and a45 == 0:
            assunto = f"[ALERTA RENOVAÇÃO] Contrato próximo de vencer - {cliente}"
            corpo = f"Atenção Comercial Globex,\n\nExiste um contrato próximo ao período de renovação.\n\nCliente: {cliente}\nNº Contrato: {num_contrato}\nData de Vencimento: {data_fim_str}\nDias restantes: {dias_restantes}"
            
            sucesso, err = enviar_email(
                st.session_state["provedor"],
                st.session_state["email_remetente"],
                st.session_state["senha_remetente"],
                st.session_state["email_comercial_globex"],
                assunto,
                corpo
            )
            if sucesso:
                c.execute("UPDATE contratos SET alerta_45_enviado = 1, status = 'Informado ao comercial por email' WHERE id = ?", (cid,))
                disparos_45 += 1

        # 30 dias -> Cliente
        elif dias_restantes <= 30 and a30 == 0:
            assunto = f"Globex Multimodal - Renovação de Contrato Nº {num_contrato}"
            corpo = f"Prezado(a) cliente {cliente},\n\nSeu contrato está chegando próximo à renovação. Aguarde que um executivo de vendas da Globex entrará em contato para renovação.\n\nAtenciosamente,\nGlobex Multimodal"
            
            sucesso, err = enviar_email(
                st.session_state["provedor"],
                st.session_state["email_remetente"],
                st.session_state["senha_remetente"],
                email_cliente,
                assunto,
                corpo
            )
            if sucesso:
                c.execute("UPDATE contratos SET alerta_30_enviado = 1, status = 'Informado ao cliente por email' WHERE id = ?", (cid,))
                disparos_30 += 1

    conn.commit()
    conn.close()
    return f"Automação executada! Avisos ao comercial: {disparos_45} | Avisos ao cliente: {disparos_30}"

# ==========================================
# BARRA LATERAL (SIDEBAR) COM LOGOTIPO
# ==========================================
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("### 🌐 GLOBEX MULTIMODAL")
    
    st.markdown("---")
    menu = ["Cadastro de Contrato", "Gestão de Contratos", "Configurações de E-mail"]
    opcao = st.radio("Menu de Navegação", menu)
    st.markdown("---")
    st.caption("© 2026 Globex Multimodal - Gestor Inteligente")

# ==========================================
# TELA 01: CADASTRO, EDIÇÃO E EXCLUSÃO
# ==========================================
if opcao == "Cadastro de Contrato":
    st.header("📝 Gestão de Cadastros de Contratos")
    st.write("Cad
