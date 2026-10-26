import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

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
    /* Estilização Geral do Fundo e Textos */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Títulos Principais */
    h1, h2, h3 {
        color: #0c3547 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* Estilização dos Botões */
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

    /* Cartões de Métricas Modernos */
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
        return "Configure as credenciais de e-mail na aba 'Configurações de E-mail' para ativar a automação."

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
# TELA 01: CADASTRO DE CONTRATO
# ==========================================
if opcao == "Cadastro de Contrato":
    st.header("📝 Cadastrar Novo Contrato")
    st.write("Preencha os dados do cliente e a vigência para iniciar o monitoramento automatizado.")
    
    with st.form("form_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            cliente = st.text_input("Nome do Cliente *")
            num_contrato = st.text_input("Número do Contrato *")
            data_inicio = st.date_input("Data de Início do Contrato", datetime.now())
        
        with col2:
            vigencia_meses = st.number_input("Vigência / Período do Reajuste (em Meses) *", min_value=1, value=12, step=1)
            email_cliente = st.text_input("E-mail do Cliente *")
            telefone_cliente = st.text_input("Telefone do Cliente *")

        data_fim_calculada = data_inicio + timedelta(days=vigencia_meses * 30)
        st.info(f"📅 **Previsão de Término / Renovação:** {data_fim_calculada.strftime('%d/%m/%Y')}")

        submitted = st.form_submit_button("💾 Salvar Contrato")
        if submitted:
            if not cliente or not num_contrato or not email_cliente:
                st.error("Por favor, preencha todos os campos obrigatórios (*).")
            else:
                conn = sqlite3.connect("contratos.db")
                c = conn.cursor()
                try:
                    c.execute('''
                        INSERT INTO contratos (cliente, num_contrato, data_inicio, vigencia_meses, data_fim, email_cliente, telefone_cliente, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (cliente, num_contrato, data_inicio, vigencia_meses, data_fim_calculada, email_cliente, telefone_cliente, "Ativo"))
                    conn.commit()
                    st.success(f"Contrato {num_contrato} cadastrado com sucesso!")
                except sqlite3.IntegrityError:
                    st.error("Erro: Este número de contrato já está cadastrado no sistema.")
                finally:
                    conn.close()

# ==========================================
# TELA 02, 03 & 04: GESTÃO DE CONTRATOS
# ==========================================
elif opcao == "Gestão de Contratos":
    st.header("📊 Painel de Gestão de Contratos")
    st.write("Acompanhe os contratos ordenados por urgência de vencimento e gerencie os status.")

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button("🔄 Executar Alertas Automáticos"):
            msg_res = executar_automacao_alertas()
            st.toast(msg_res)
            st.rerun()

    conn = sqlite3.connect("contratos.db")
    df = pd.read_sql_query("SELECT * FROM contratos", conn)
    conn.close()

    if df.empty:
        st.warning("Nenhum contrato cadastrado até o momento.")
    else:
        hoje = datetime.now().date()
        df['data_fim_dt'] = pd.to_datetime(df['data_fim']).dt.date
        df['dias_restantes'] = df['data_fim_dt'].apply(lambda x: (x - hoje).days)
        
        # Ordenação automática: os que vão vencer primeiro aparecem nas linhas superiores
        df = df.sort_values(by='dias_restantes', ascending=True)

        # Indicadores Visuais Rápidos no Topo
        total_contratos = len(df)
        vencendo_breve = len(df[df['dias_restantes'] <= 45])
        
        mcol1, mcol2 = st.columns(2)
        with mcol1:
            st.markdown(f"""
                <div class="metric-card">
                    <h3 style="margin:0; color:#0c3547;">{total_contratos}</h3>
                    <p style="margin:0; color:#666;">Total de Contratos Monitorados</p>
                </div>
            """, unsafe_allow_html=True)
        with mcol2:
            st.markdown(f"""
                <div class="metric-card metric-card-alert">
                    <h3 style="margin:0; color:#d90429;">{vencendo_breve}</h3>
                    <p style="margin:0; color:#666;">Contratos Próximos de Vencer (≤ 45 dias)</p>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📋 Lista Geral de Contratos (Ordem Decrescente de Urgência)")
        
        display_df = df[['id', 'cliente', 'num_contrato', 'data_inicio', 'vigencia_meses', 'data_fim', 'dias_restantes', 'status']].copy()
        display_df.columns = ['ID', 'Cliente', 'Nº Contrato', 'Início', 'Vigência (Meses)', 'Vencimento', 'Dias p/ Vencer', 'Status Atual']
        st.dataframe(display_df, use_container_width=True)

        st.divider()
        st.subheader("⚙️ Atualização Manual de Status e Renovação")

        contrato_id = st.selectbox("Selecione o Contrato:", df['id'].tolist(), format_func=lambda x: f"ID {x} - {df[df['id']==x]['cliente'].values[0]} (Contrato: {df[df['id']==x]['num_contrato'].values[0]})")
        
        contrato_atual = df[df['id'] == contrato_id].iloc[0]

        st.info(f"**Cliente Selecionado:** {contrato_atual['cliente']} | **Status Atual:** `{contrato_atual['status']}` | **Vencimento:** {contrato_atual['data_fim']}")

        opcoes_status = [
            "Ativo",
            "Informado ao comercial por email",
            "Informado ao cliente por email",
            "Em negociação com o cliente",
            "Finalizado"
        ]
        
        idx_def = opcoes_status.index(contrato_atual['status']) if contrato_atual['status'] in opcoes_status else 0
        novo_status = st.selectbox("Selecione o Novo Status:", opcoes_status, index=idx_def)

        # Regra do Finalizado (Renovação de Ciclo em Meses ou Manual)
        if novo_status == "Finalizado":
            st.warning("🔄 **Renovação de Ciclo:** Ao finalizar, o sistema configurará a nova data de início e reiniciará o ciclo de contagem por meses.")
            
            tipo_reajuste = st.radio("Forma de reajuste do próximo ciclo:", ["Manter Vigência em Meses", "Ajustar Data Fim Manualmente"])
            
            nova_data_inicio = datetime.now().date()
            if tipo_reajuste == "Manter Vigência em Meses":
                novos_meses = st.number_input("Nova Vigência (em meses)", min_value=1, value=int(contrato_atual['vigencia_meses']))
                nova_data_fim = nova_data_inicio + timedelta(days=novos_meses * 30)
            else:
                novos_meses = contrato_atual['vigencia_meses']
                nova_data_fim = st.date_input("Nova Data Fim do Contrato", nova_data_inicio + timedelta(days=365))

            if st.button("✅ Confirmar Renovação e Reiniciar Ciclo"):
                conn = sqlite3.connect("contratos.db")
                c = conn.cursor()
                c.execute('''
                    UPDATE contratos 
                    SET status = 'Ativo',
                        data_inicio = ?,
                        vigencia_meses = ?,
                        data_fim = ?,
                        alerta_45_enviado = 0,
                        alerta_30_enviado = 0
                    WHERE id = ?
                ''', (nova_data_inicio, novos_meses, nova_data_fim, contrato_id))
                conn.commit()
                conn.close()
                st.success("Contrato renovado e ciclo reiniciado com sucesso!")
                st.rerun()

        else:
            if st.button("💾 Salvar Alteração de Status"):
                conn = sqlite3.connect("contratos.db")
                c = conn.cursor()
                c.execute("UPDATE contratos SET status = ? WHERE id = ?", (novo_status, contrato_id))
                conn.commit()
                conn.close()
                st.success("Status atualizado com sucesso!")
                st.rerun()

# ------------------------------------------
# TELA 05: CONFIGURAÇÕES DE E-MAIL
# ------------------------------------------
elif opcao == "Configurações de E-mail":
    st.header("⚙️ Configurações de Conexão de E-mail")
    st.write("Configure abaixo as credenciais de envio para automatizar os disparos do Outlook ou Gmail.")

    provedor = st.selectbox("Provedor de E-mail", ["Outlook / Office365", "Gmail"])
    email_remetente = st.text_input("E-mail Remetente (Automação)", value=st.session_state.get("email_remetente", ""))
    senha_remetente = st.text_input("Senha / Senha de App", type="password", value=st.session_state.get("senha_remetente", ""))
    email_comercial = st.text_input("E-mail do Comercial Globex (Destinatário do alerta de 45 dias)", value=st.session_state.get("email_comercial_globex", ""))

    if st.button("💾 Salvar Configurações de E-mail"):
        st.session_state["provedor"] = provedor
        st.session_state["email_remetente"] = email_remetente
        st.session_state["senha_remetente"] = senha_remetente
        st.session_state["email_comercial_globex"] = email_comercial
        st.success("Configurações salvas com sucesso no sistema!")
