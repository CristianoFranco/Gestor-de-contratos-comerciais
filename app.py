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
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0c3547 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stButton>button { background-color: #0c3547; color: white; border-radius: 8px; border: none; padding: 0.5rem 1rem; font-weight: 600; transition: 0.3s; }
    .stButton>button:hover { background-color: #00b4d8; color: #0c3547; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 5px solid #00b4d8; text-align: center; }
    .metric-card-alert { border-left: 5px solid #d90429; }
    </style>
""", unsafe_allow_html=True)

def init_db():
    conn = sqlite3.connect("contratos.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT NOT NULL, num_contrato TEXT UNIQUE NOT NULL, data_inicio DATE NOT NULL, vigencia_meses INTEGER NOT NULL, data_fim DATE NOT NULL, email_cliente TEXT NOT NULL, telefone_cliente TEXT NOT NULL, status TEXT NOT NULL, alerta_45_enviado INTEGER DEFAULT 0, alerta_30_enviado INTEGER DEFAULT 0)")
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
    if "email_remetente" not in st.session_state or not st.session_state["email_remetente"]:
        return "Configure as credenciais de e-mail na aba Configurações de E-mail."

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
        data_fim_br = data_fim.strftime("%d/%m/%Y")
        dias_restantes = (data_fim - hoje).days

        # 45 dias -> Comercial Globex
        if dias_restantes <= 45 and dias_restantes > 30 and a45 == 0:
            assunto = f"[ALERTA RENOVAÇÃO] Contrato próximo de vencer - {cliente}"
            corpo = f"Atenção Comercial Globex,\n\nExiste um contrato próximo ao período de renovação.\n\nCliente: {cliente}\nNº Contrato: {num_contrato}\nData de Vencimento: {data_fim_br}\nDias restantes: {dias_restantes}"
            
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
            corpo = f"Prezado(a) cliente {cliente},\n\nSeu contrato está chegando próximo à renovação. Aguarde contato da Globex.\n\nAtenciosamente,\nGlobex Multimodal"
            
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
    return f"Automação executada! Comercial: {disparos_45} | Cliente: {disparos_30}"

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
    opcao = st.radio("Navegação", menu)
    st.markdown("---")
    st.caption("© 2026 Globex Multimodal")

# ==========================================
# TELA 01: CADASTRO, EDIÇÃO E EXCLUSÃO
# ==========================================
if opcao == "Cadastro de Contrato":
    st.header("📝 Gestão de Cadastros de Contratos")
    st.write("Cadastre novos contratos ou gerencie os registos existentes.")
    
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

        # Cálculo dinâmico e exato de meses
        total_meses = int(vigencia_meses)
        anos_extras = total_meses // 12
        meses_extras = total_meses % 12
        
        ano_alvo = data_inicio.year + anos_extras + (data_inicio.month + meses_extras - 1) // 12
        mes_alvo = (data_inicio.month + meses_extras - 1) % 12 + 1
        dia_alvo = data_inicio.day
        
        ultimo_dia_mes_alvo = calendar.monthrange(ano_alvo, mes_alvo)[1]
        if dia_alvo > ultimo_dia_mes_alvo:
            dia_alvo = ultimo_dia_mes_alvo
            
        data_fim_calculada = datetime(ano_alvo, mes_alvo, dia_alvo).date()

        st.info(f"📅 Previsão de Término / Renovação: {data_fim_calculada.strftime('%d/%m/%Y')}")

        if st.button("💾 Salvar Contrato", key="btn_salvar_novo"):
            if not cliente or not num_contrato or not email_cliente:
                st.error("Por favor, preencha todos os campos obrigatórios (*).")
            else:
                conn = sqlite3.connect("contratos.db")
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO contratos (cliente, num_contrato, data_inicio, vigencia_meses, data_fim, email_cliente, telefone_cliente, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (cliente, num_contrato, str(data_inicio), vigencia_meses, str(data_fim_calculada), email_cliente, telefone_cliente, "Ativo"))
                    conn
