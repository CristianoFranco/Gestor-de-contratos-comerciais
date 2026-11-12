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
                num_contrato = st.text_input("Número do Contrato *", key="input_novo_num")
                data_inicio = st.date_input("Data de Início do Contrato", datetime.now(), key="input_novo_inicio")
            with col2:
                email_cliente = st.text_input("E-mail do Cliente *", key="input_novo_email")
                telefone_cliente = st.text_input("Telefone do Cliente *", key="input_novo_tel")
                vigencia_meses = st.number_input("Vigência / Período do Reajuste (em Meses) *", min_value=1, value=12, key="input_novo_vigencia")

            try:
                anos = vigencia_meses // 12
                meses_restantes = vigencia_meses % 12
                data_fim = data_inicio
                for _ in range(anos):
                    data_fim = data_fim.replace(year=data_fim.year + 1)
                for _ in range(meses_restantes):
                    novo_mes = data_fim.month % 12 + 1
                    novo_ano = data_fim.year + (1 if data_fim.month == 12 else 0)
                    ultimo_dia = calendar.monthrange(novo_ano, novo_mes)[1]
                    dia = min(data_fim.day, ultimo_dia)
                    data_fim = data_fim.replace(year=novo_ano, month=novo_mes, day=dia)
            except Exception:
                data_fim = data_inicio + timedelta(days=365)

            st.info(f"📅 Previsão de Término / Renovação: {data_fim.strftime('%d/%m/%Y')}")

            if st.button("💾 Salvar Contrato", key="btn_salvar_novo_contrato"):
                if not nome_cliente or not email_cliente or not num_contrato:
                    st.error("Por favor, preencha todos os campos obrigatórios (*).")
                else:
                    try:
                        novo_reg = {
                            "cliente": nome_cliente,
                            "email_cliente": email_cliente,
                            "num_contrato": num_contrato,
                            "telefone": telefone_cliente,
                            "data_inicio": str(data_inicio),
                            "vigencia_meses": int(vigencia_meses),
                            "data_fim": str(data_fim),
                            "status": "Ativo",
                            "alerta_45_enviado": 0,
                            "alerta_30_enviado": 0
                        }
                        supabase.table("contratos").insert(novo_reg).execute()
                        st.success("Contrato guardado com sucesso!")
                        
                        st.session_state["input_novo_cliente"] = ""
                        st.session_state["input_novo_email"] = ""
                        st.session_state["input_novo_num"] = ""
                        st.session_state["input_novo_tel"] = ""
                        st.session_state["input_novo_vigencia"] = 12
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar contrato: {e}")

        with aba_editar:
            st.subheader("Editar / Excluir Contrato Existente")

            try:
                res_all = supabase.table("contratos").select("*").execute()
                lista_db = res_all.data if res_all and res_all.data else []
            except Exception:
                lista_db = []

            if not lista_db:
                st.info("Nenhum contrato registado para edição.")
            else:
                contrato_selecionado = st.selectbox(
                    "Selecione o Contrato:",
                    lista_db,
                    format_func=lambda c: f"ID {c['id']} - {c['cliente']} ({c['num_contrato']})",
                    key="select_contrato_editar"
                )

                if contrato_selecionado:
                    cid = contrato_selecionado['id']
                    
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        st.text_input("Nome do Cliente (Fixo)", value=contrato_selecionado['cliente'], disabled=True)
                        edit_num = st.text_input("Número do Contrato", value=contrato_selecionado['num_contrato'], key="edit_num_contrato")
                        
                        dt_inicio_db = datetime.strptime(contrato_selecionado['data_inicio'], "%Y-%m-%d").date()
                        edit_inicio = st.date_input("Data de Início", value=dt_inicio_db, key="edit_data_inicio")

                    with col_e2:
                        edit_email = st.text_input("E-mail do Cliente *", value=contrato_selecionado['email_cliente'], key="edit_email_cliente")
                        edit_tel = st.text_input("Telefone do Cliente *", value=contrato_selecionado.get('telefone', ''), key="edit_tel_cliente")
                        
                        vig_db = int(contrato_selecionado.get('vigencia_meses', 12))
                        edit_vig = st.number_input("Vigência (Meses) *", min_value=1, value=vig_db, key="edit_vigencia_meses")

                    usar_manual = st.checkbox("Definir Data Limite de Vigência Manualmente (Término Antecipado / Rescisão)", key="edit_usar_manual")

                    if usar_manual:
                        dt_fim_db = datetime.strptime(contrato_selecionado['data_fim'], "%Y-%m-%d").date()
                        edit_data_fim = st.date_input("Nova Data Fim (Rescisão / Término Manual)", value=dt_fim_db, key="edit_data_fim_manual")
                    else:
                        try:
                            anos = edit_vig // 12
                            meses_restantes = edit_vig % 12
                            edit_data_fim = edit_inicio
                            for _ in range(anos):
                                edit_data_fim = edit_data_fim.replace(year=edit_data_fim.year + 1)
                            for _ in range(meses_restantes):
                                novo_mes = edit_data_fim.month % 12 + 1
                                novo_ano = edit_data_fim.year + (1 if edit_data_fim.month == 12 else 0)
                                ultimo_dia = calendar.monthrange(novo_ano, novo_mes)[1]
                                dia = min(edit_data_fim.day, ultimo_dia)
                                edit_data_fim = edit_data_fim.replace(year=novo_ano, month=novo_mes, day=dia)
                        except Exception:
                            edit_data_fim = edit_inicio + timedelta(days=365)
                        st.info(f"📅 Nova Data Fim Recalculada pela Vigência: {edit_data_fim.strftime('%d/%m/%Y')}")

                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button("💾 Salvar Alterações", key="btn_salvar_alteracoes_contrato"):
                            try:
                                dados_up = {
                                    "num_contrato": edit_num,
                                    "email_cliente": edit_email,
                                    "telefone": edit_tel,
                                    "data_inicio": str(edit_inicio),
                                    "vigencia_meses": int(edit_vig),
                                    "data_fim": str(edit_data_fim)
                                }
                                supabase.table("contratos").update(dados_up).eq("id", cid).execute()
                                st.success("Contrato atualizado com sucesso!")
                                
                                st.session_state["edit_email_cliente"] = ""
                                st.session_state["edit_tel_cliente"] = ""
                                st.session_state["edit_num_contrato"] = ""
                                st.session_state["edit_vigencia_meses"] = 12
                                
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar: {e}")
                    with col_b2:
                        if st.button("🗑️ Excluir Contrato", key="btn_excluir_contrato"):
                            try:
                                supabase.table("contratos").delete().eq("id", cid).execute()
                                st.success("Contrato excluído com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")

    elif opcao == "Gestão de Contratos":
        st.markdown("<h1 style='text-align: center; color: #0c3547;'>📊 Painel de Contratos Ativos</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Acompanhe os prazos de vigência, status e gerencie renovações ou encerramentos.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        try:
            df = pd.DataFrame()
            response = supabase.table("contratos").select("*").execute()
            if response and response.data:
                df = pd.DataFrame(response.data)

            if df.empty:
                st.info("Nenhum contrato registado.")
            else:
                hoje = datetime.now().date()
                dias_p_vencer = []
                for _, row in df.iterrows():
                    d_fim = datetime.strptime(row['data_fim'], "%Y-%m-%d").date()
                    dias_p_vencer.append((d_fim - hoje).days)
                
                df['dias_restantes'] = dias_p_vencer

                vencidos = df[df['dias_restantes'] < 0]
                total_contratos = len(df)
                vencendo_breve = len(df[(df['dias_restantes'] >= 0) & (df['dias_restantes'] <= 45)])

                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.markdown(f"""
                        <div class="metric-card">
                            <h3>Total de Contratos</h3>
                            <h1 style="color: #0c3547;">{total_contratos}</h1>
                        </div>
                    """, unsafe_allow_html=True)
                with col_m2:
                    st.markdown(f"""
                        <div class="metric-card metric-card-alert">
                            <h3>Vencendo em breve / Vencidos ($\le 45$ dias)</h3>
                            <h1 style="color: #d90429;">{vencendo_breve + len(vencidos)}</h1>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("📋 Lista Geral de Contratos")

                if not vencidos.empty:
                    st.warning(f"⚠️ Atenção: Existem **{len(vencidos)}** contrato(s) com prazo de vigência vencido destacados em vermelho!")

                display_df = df[['id', 'cliente', 'num_contrato', 'data_inicio', 'vigencia_meses', 'data_fim', 'dias_restantes', 'status']].copy()
                display_df['data_inicio'] = pd.to_datetime(display_df['data_inicio']).dt.strftime('%d/%m/%Y')
                display_df['data_fim'] = pd.to_datetime(display_df['data_fim']).dt.strftime('%d/%m/%Y')
                
                display_df.columns = ['ID', 'Cliente', 'Nº Contrato', 'Início', 'Vigência (Meses)', 'Vencimento', 'Dias p/ Vencer', 'Status Atual']
                
                def colorir_linhas_contrato(row_data):
                    idx = row_data.name
                    dias = df.loc[idx, 'dias_restantes']
                    if dias < 0:
                        return ['background-color: #ffe6e6'] * len(row_data)  # Vermelho claro para vencidos
                    elif 0 <= dias <= 45:
                        return ['background-color: #fff3cd'] * len(row_data)  # Amarelo claro para 0 a 45 dias
                    return [''] * len(row_data)

                st.dataframe(display_df.style.apply(colorir_linhas_contrato, axis=1), use_container_width=True, hide_index=True)

                st.divider()
                st.subheader("⚙️ Atualização de Status e Renovação")

                contrato_id = st.selectbox(
                    "Selecione
