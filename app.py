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
    remetente = st.session_state.get("email_remetente") or config_db.get("email_remetente")
    senha = st.session_state.get("senha_remetente") or config_db.get("senha_remetente")
    prov = st.session_state.get("provedor") or config_db.get("provedor", "Outlook / Office365")
    comercial = st.session_state.get("email_comercial_globex") or config_db.get("email_comercial_globex")

    if not remetente or not senha:
        return "Configure as credenciais de e-mail na aba Configurações de E-mail."

    if not supabase:
        return "Erro de conexão com o Supabase."

    try:
        response = supabase.table("contratos").select("*").execute()
        contratos = response.data

        hoje = datetime.now().date()
        disparos_45 = 0
        disparos_30 = 0

        for item in contratos:
            cid = item['id']
            cliente = item['cliente']
            num_contrato = item['num_contrato']
            data_fim_str = item['data_fim']
            email_cliente = item['email_cliente']
            a45 = item['alerta_45_enviado']
            a30 = item['alerta_30_enviado']
            
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
            data_fim_br = data_fim.strftime("%d/%m/%Y")
            dias_restantes = (data_fim - hoje).days

            # 45 dias -> Comercial Globex
            if dias_restantes <= 45 and dias_restantes > 30 and a45 == 0:
                assunto = f"[ALERTA RENOVAÇÃO] Contrato próximo de vencer - {cliente}"
                corpo = f"Atenção Comercial Globex,\n\nExiste um contrato próximo ao período de renovação.\n\nCliente: {cliente}\nNº Contrato: {num_contrato}\nData de Vencimento: {data_fim_br}\nDias restantes: {dias_restantes}"
                
                sucesso, err = enviar_email(prov, remetente, senha, comercial, assunto, corpo)
                if sucesso:
                    supabase.table("contratos").update({"alerta_45_enviado": 1, "status": "Informado ao comercial por email"}).eq("id", cid).execute()
                    disparos_45 += 1

            # 30 dias -> Cliente
            elif dias_restantes <= 30 and a30 == 0:
                assunto = f"Globex Multimodal - Renovação de Contrato Nº {num_contrato}"
                corpo = f"Prezado(a) cliente {cliente},\n\nSeu contrato está chegando próximo à renovação. Aguarde contato da Globex.\n\nAtenciosamente,\nGlobex Multimodal"
                
                sucesso, err = enviar_email(prov, remetente, senha, email_cliente, assunto, corpo)
                if sucesso:
                    supabase.table("contratos").update({"alerta_30_enviado": 1, "status": "Informado ao cliente por email"}).eq("id", cid).execute()
                    disparos_30 += 1

        if disparos_45 > 0 or disparos_30 > 0:
            return f"Automação executada com sucesso! Comercial: {disparos_45} | Cliente: {disparos_30}"
        return "Nenhum alerta pendente no momento."
    except Exception as e:
        return f"Erro na automação: {e}"

# ==========================================
# BARRA LATERAL (SIDEBAR)
# ==========================================
with st.sidebar:
    caminho_logo_side = "Logo.png" if os.path.exists("Logo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if caminho_logo_side:
        st.image(caminho_logo_side, use_container_width=True)
    else:
        st.markdown("### 🌐 GLOBEX MULTIMODAL")
    
    st.markdown("---")
    menu = ["Cadastro de Contrato", "Gestão de Contratos", "Configurações de E-mail"]
    opcao = st.radio("Navegação", menu)
    st.markdown("---")
    st.caption("© 2026 Globex Multimodal")

# ==========================================
# TELA 01: CADASTRO, EDIÇÃO E EXCLUSÃO
# ==========================================
if opcao == "Cadastro de Contrato":
    st.markdown("<h1 style='text-align: center; color: #0c3547;'>📝 Gestão de Cadastros de Contratos</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Cadastre novos contratos ou gerencie os registos existentes.</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    tab_cad, tab_edit = st.tabs(["➕ Novo Contrato", "✏️ Editar / Excluir Contrato"])
    
    with tab_cad:
        st.subheader("Novo Contrato")
        col1, col2 = st.columns(2)
        with col1:
            cliente = st.text_input("Nome do Cliente *", key="cad_cliente")
            num_contrato = st.text_input("Número do Contrato *", key="cad_num")
            data_inicio = st.date_input("Data de Início do Contrato", datetime.now(), key="cad_data_inicio")
        
        with col2:
            email_cliente = st.text_input("E-mail do Cliente *", key="cad_email")
            telefone_cliente = st.text_input("Telefone do Cliente *", key="cad_tel")
            vigencia_meses = st.number_input("Vigência / Período do Reajuste (em Meses) *", min_value=1, value=12, step=1, key="cad_vigencia")

        total_meses = int(vigencia_meses)
        anos_extras = total_meses // 12
        meses_extras = total_meses % 12
        
        ano_alvo = data_inicio.year + anos_extras + (data_inicio.month + meses_extras - 1) // 12
        mes_alvo = (data_
