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

        # Cálculo dinâmico e exato de meses (atualiza na hora ao mexer em vigência ou data)
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
                    c.execute('''
                        INSERT INTO contratos (cliente, num_contrato, data_inicio, vigencia_meses, data_fim, email_cliente, telefone_cliente, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (cliente, num_contrato, data_inicio, vigencia_meses, data_fim_calculada, email_cliente, telefone_cliente, "Ativo"))
                    conn.commit()
                    st.success("Contrato cadastrado com sucesso!")
                except sqlite3.IntegrityError:
                    st.error("Erro: Número de contrato já cadastrado.")
                finally:
                    conn.close()

    with tab_edit:
        conn = sqlite3.connect("contratos.db")
        df_edit = pd.read_sql_query("SELECT * FROM contratos", conn)
        conn.close()
        
        if df_edit.empty:
            st.info("Nenhum contrato cadastrado.")
        else:
            cid_edit = st.selectbox(
                "Selecione o Contrato:",
                df_edit['id'].tolist(),
                format_func=lambda x: f"ID {x} - {df_edit[df_edit['id']==x]['cliente'].values[0]} ({df_edit[df_edit['id']==x]['num_contrato'].values[0]})"
            )
            
            c_data = df_edit[df_edit['id'] == cid_edit].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                novo_cliente = st.text_input("Nome do Cliente *", value=c_data['cliente'], key="edit_cliente")
                novo_num_contrato = st.text_input("Número do Contrato *", value=c_data['num_contrato'], key="edit_num")
                data_inicio_edit = st.date_input("Data de Início", value=datetime.strptime(c_data['data_inicio'], "%Y-%m-%d").date(), key="edit_data")
            with col2:
                novo_email = st.text_input("E-mail do Cliente *", value=c_data['email_cliente'], key="edit_email")
                novo_tel = st.text_input("Telefone do Cliente *", value=c_data['telefone_cliente'], key="edit_tel")
                nova_vigencia = st.number_input("Vigência (Meses) *", min_value=1, value=int(c_data['vigencia_meses']), step=1, key="edit_vigencia")
            
            t_meses = int(nova_vigencia)
            a_extras = t_meses // 12
            m_extras = t_meses % 12
            a_alvo = data_inicio_edit.year + a_extras + (data_inicio_edit.month + m_extras - 1) // 12
            m_alvo = (data_inicio_edit.month + m_extras - 1) % 12 + 1
            d_alvo = data_inicio_edit.day
            ultimo_d = calendar.monthrange(a_alvo, m_alvo)[1]
            if d_alvo > ultimo_d:
                d_alvo = ultimo_d
            nova_data_fim = datetime(a_alvo, m_alvo, d_alvo).date()

            st.info(f"📅 Nova Data Fim Recalculada: {nova_data_fim.strftime('%d/%m/%Y')}")
            
            if st.button("💾 Salvar Alterações", key="btn_salvar_edit"):
                if not novo_cliente or not novo_num_contrato or not novo_email:
                    st.error("Preencha todos os campos obrigatórios (*).")
                else:
                    conn = sqlite3.connect("contratos.db")
                    cursor = conn.cursor()
                    try:
                        cursor.execute('''
                            UPDATE contratos 
                            SET cliente = ?, num_contrato = ?, data_inicio = ?, vigencia_meses = ?, data_fim = ?, email_cliente = ?, telefone_cliente = ?
                            WHERE id = ?
                        ''', (novo_cliente, novo_num_contrato, data_inicio_edit, nova_vigencia, nova_data_fim, novo_email, novo_tel, cid_edit))
                        conn.commit()
                        conn.close()
                        st.success("Atualizado com sucesso!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        conn.close()
                        st.error("Erro: Número de contrato duplicado.")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("---")
            st.subheader("⚠️ Zona de Exclusão")
            
            if st.button("🗑️ Excluir Contrato Permanentemente", key="btn_excluir"):
                conn = sqlite3.connect("contratos.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM contratos WHERE id = ?", (cid_edit,))
                conn.commit()
                conn.close()
                st.success("Contrato excluído!")
                st.rerun()

# ==========================================
# TELA 02, 03 & 04: GESTÃO DE CONTRATOS
# ==========================================
elif opcao == "Gestão de Contratos":
    st.header("📊 Painel de Gestão de Contratos")
    st.write("Acompanhe os contratos ordenados por urgência.")

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button("🔄 Executar Alertas"):
            msg_res = executar_automacao_alertas()
            st.toast(msg_res)
            st.rerun()

    conn = sqlite3.connect("contratos.db")
    df = pd.read_sql_query("SELECT * FROM contratos", conn)
    conn.close()

    if df.empty:
        st.warning("Nenhum contrato cadastrado.")
    else:
        hoje = datetime.now().date()
        df['data_fim_dt'] = pd.to_datetime(df['data_fim']).dt.date
        df['dias_restantes'] = df['data_fim_dt'].apply(lambda x: (x - hoje).days)
        
        df = df.sort_values(by='dias_restantes', ascending=True)

        total_contratos = len(df)
        vencendo_breve = len(df[df['dias_restantes'] <= 45])
        
        mcol1, mcol2 = st.columns(2)
        with mcol1:
            st.markdown(f"""
                <div class="metric-card">
                    <h3 style="margin:0; color:#0c3547;">{total_contratos}</h3>
                    <p style="margin:0; color:#666;">Total de Contratos</p>
                </div>
            """, unsafe_allow_html=True)
        with mcol2:
            st.markdown(f"""
                <div class="metric-card metric-card-alert">
                    <h3 style="margin:0; color:#d90429;">{vencendo_breve}</h3>
                    <p style="margin:0; color:#666;">Vencendo em breve (≤ 45 dias)</p>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📋 Lista Geral de Contratos")
        
        display_df = df[['id', 'cliente', 'num_contrato', 'data_inicio', 'vigencia_meses', 'data_fim', 'dias_restantes', 'status']].copy()
        display_df.columns = ['ID', 'Cliente', 'Nº Contrato', 'Início', 'Vigência (Meses)', 'Vencimento', 'Dias p/ Vencer', 'Status Atual']
        st.dataframe(display_df, use_container_width=True)

        st.divider()
        st.subheader("⚙️ Atualização de Status e Renovação")

        contrato_id = st.selectbox("Selecione o Contrato:", df['id'].tolist(), format_func=lambda x: f"ID {x} - {df[df['id']==x]['cliente'].values[0]} ({df[df['id']==x]['num_contrato'].values[0]})")
        
        contrato_atual = df[df['id'] == contrato_id].iloc[0]

        st.info(f"Cliente: {contrato_atual['cliente']} | Status: `{contrato_atual['status']}` | Vencimento: {contrato_atual['data_fim']}")

        opcoes_status = [
            "Ativo",
            "Informado ao comercial por email",
            "Informado ao cliente por email",
            "Em negociação com o cliente",
            "Finalizado"
        ]
        
        idx_def = opcoes_status.index(contrato_atual['status']) if contrato_atual['status'] in opcoes_status else 0
        novo_status = st.selectbox("Novo Status:", opcoes_status, index=idx_def)

        if novo_status == "Finalizado":
            st.warning("🔄 Ao finalizar, o contrato será renovado para o próximo ciclo.")
            
            tipo_reajuste = st.radio("Reajuste:", ["Manter Vigência em Meses", "Ajustar Data Fim Manualmente"])
            
            nova_data_inicio = datetime.now().date()
            if tipo_reajuste == "Manter Vigência em Meses":
                novos_meses = st.number_input("Nova Vigência (meses)", min_value=1, value=int(contrato_atual['vigencia_meses']))
                
                t_m = int(novos_meses)
                a_e = t_m // 12
                m_e = t_m % 12
                a_a = nova_data_inicio.year + a_e + (nova_data_inicio.month + m_e - 1) // 12
                m_a = (nova_data_inicio.month + m_e - 1) % 12 + 1
                d_a = nova_data_inicio.day
                ultimo_d_a = calendar.monthrange(a_a, m_a)[1]
                if d_a > ultimo_d_a:
                    d_a = ultimo_d_a
                nova_data_fim = datetime(a_a, m_a, d_a).date()
            else:
                novos_meses = contrato_atual['vigencia_meses']
                nova_data_fim = st.date_input("Nova Data Fim", nova_data_inicio + timedelta(days=365))

            if st.button("✅ Confirmar Renovação"):
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
                st.success("Contrato renovado com sucesso!")
                st.rerun()

        else:
            if st.button("💾 Salvar Status"):
                conn = sqlite3.connect("contratos.db")
                c = conn.cursor()
                c.execute("UPDATE contratos SET status = ? WHERE id = ?", (novo_status, contrato_id))
                conn.commit()
                conn.close()
                st.success("Status atualizado!")
                st.rerun()

# ------------------------------------------
# TELA 05: CONFIGURAÇÕES DE E-MAIL
# ------------------------------------------
elif opcao == "Configurações de E-mail":
    st.header("⚙️ Configurações de E-mail")
    st.write("Configure as credenciais para disparos automáticos.")

    provedor = st.selectbox("Provedor", ["Outlook / Office365", "Gmail"])
    email_remetente = st.text_input("E-mail Remetente", value=st.session_state.get("email_remetente", ""))
    senha_remetente = st.text_input("Senha / Senha de App", type="password", value=st.session_state.get("senha_remetente", ""))
    email_comercial = st.text_input("E-mail do Comercial Globex", value=st.session_state.get("email_comercial_globex", ""))

    if st.button("💾 Salvar Configurações"):
        st.session_state["provedor"] = provedor
        st.session_state["email_remetente"] = email_remetente
        st.session_state["senha_remetente"] = senha_remetente
        st.session_state["email_comercial_globex"] = email_comercial
        st.success("Configurações salvas!")
