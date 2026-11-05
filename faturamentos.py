import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import calendar

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

    # Conexão Supabase
    @st.cache_resource
    def init_supabase():
        try:
            from supabase import create_client
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
            return create_client(url, key)
        except Exception as e:
            st.error(f"Erro ao conectar ao Supabase: {e}")
            return None

    supabase = init_supabase()

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

    def ajustar_dia_util(data_obj, direcao="retroceder"):
        while data_obj.weekday() >= 5:  # Sábado (5) ou Domingo (6)
            if direcao == "retroceder":
                data_obj -= timedelta(days=1)
            else:
                data_obj += timedelta(days=1)
        return data_obj

    def calcular_previsao_faturamento(condicao, inicio_dt, dia_fixo=10):
        if isinstance(inicio_dt, str):
            inicio_dt = datetime.strptime(inicio_dt, "%Y-%m-%d").date()

        if condicao == "30 dias após inicio":
            data_fatura = inicio_dt + timedelta(days=30)
            data_fatura = ajustar_dia_util(data_fatura, "avancar")
        elif condicao == "Data Fixa":
            d_fixo = min(int(dia_fixo), calendar.monthrange(inicio_dt.year, inicio_dt.month)[1])
            data_fatura = datetime(inicio_dt.year, inicio_dt.month, d_fixo).date()
            data_fatura = ajustar_dia_util(data_fatura, "retroceder")
        elif condicao == "Penúltimo dia do mês":
            ultimo_dia = calendar.monthrange(inicio_dt.year, inicio_dt.month)[1]
            data_fatura = datetime(inicio_dt.year, inicio_dt.month, ultimo_dia - 1).date()
            data_fatura = ajustar_dia_util(data_fatura, "retroceder")
        elif condicao == "Fim do mês":
            ultimo_dia = calendar.monthrange(inicio_dt.year, inicio_dt.month)[1]
            data_fatura = datetime(inicio_dt.year, inicio_dt.month, ultimo_dia).date()
            data_fatura = ajustar_dia_util(data_fatura, "retroceder")
        elif condicao == "1º dia útil do mês":
            data_fatura = datetime(inicio_dt.year, inicio_dt.month, 1).date()
            data_fatura = ajustar_dia_util(data_fatura, "avancar")
        else:
            data_fatura = inicio_dt
        return data_fatura

    def executar_automacao_faturamentos():
        remetente = config_db.get("email_remetente")
        senha = config_db.get("senha_remetente")
        prov = config_db.get("provedor", "Outlook / Office365")

        if not remetente or not senha or not supabase:
            return "Credenciais de e-mail ou Supabase não configuradas."

        try:
            response = supabase.table("faturamentos").select("*").eq("status", "Ativo").execute()
            registros = response.data

            hoje = datetime.now().date()
            disparos = 0

            for item in registros:
                rid = item['id']
                cliente = item['cliente']
                condicao = item['condicao']
                inicio_str = item['inicio_periodo']
                email_cliente = item['email_cliente']
                alerta_enviado = item.get('alerta_enviado', 0)
                dia_fixo = item.get('dia_fixo', 10)

                inicio_dt = datetime.strptime(inicio_str, "%Y-%m-%d").date()
                data_fatura = calcular_previsao_faturamento(condicao, inicio_dt, dia_fixo)

                dias_restantes = (data_fatura - hoje).days

                if dias_restantes in [2, 1] and alerta_enviado < 2:
                    assunto = f"[ALERTA OPERACIONAL] Preparação de Faturamento - {cliente}"
                    corpo = f"Atenção Equipa Operacional,\n\nO faturamento para o cliente {cliente} (Condição: {condicao}) tem data prevista para {data_fatura.strftime('%d/%m/%Y')}.\nFaltam {dias_restantes} dia(s) para a data limite de preparação de dados.\n\nAtenciosamente,\nGlobex Multimodal"
                    
                    sucesso, err = enviar_email(prov, remetente, senha, email_cliente, assunto, corpo)
                    if sucesso:
                        supabase.table("faturamentos").update({"alerta_enviado": alerta_enviado + 1}).eq("id", rid).execute()
                        disparos += 1

            if disparos > 0:
                return f"Automação executada! {disparos} alerta(s) operacional(is) enviado(s)."
            return "Nenhum alerta de faturamento pendente para hoje."
        except Exception as e:
            return f"Erro na automação: {e}"

    # Barra lateral
    with st.sidebar:
        caminho_logo_side = "Logo.png" if os.path.exists("Logo.png") else ("logo.png" if os.path.exists("logo.png") else None)
        if caminho_logo_side:
            st.image(caminho_logo_side, use_container_width=True)
        else:
            st.markdown("### 🌐 GLOBEX MULTIMODAL")
        
        st.markdown("---")
        menu = ["Novo Faturamento", "Painel de Faturamentos Ativos"]
        opcao = st.radio("Navegação Faturamentos", menu)
        st.markdown("---")
        st.caption("© 2026 Globex Multimodal")

    # Tela 1: Novo Faturamento (Apenas vinculado ao Gestor de Contratos)
    if opcao == "Novo Faturamento":
        st.markdown("<h1 style='text-align: center; color: #0c3547;'>📝 Configuração de Faturamento</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Registe as regras de faturamento vinculadas aos Contratos cadastrados.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        try:
            res_contratos = supabase.table("contratos").select("*").execute()
            lista_contratos = res_contratos.data
        except Exception:
            lista_contratos = []

        if not lista_contratos:
            st.warning("⚠️ Nenhum contrato encontrado na base de dados. Por favor, cadastre primeiro um contrato no 'Gestor de Contratos'.")
        else:
            contrato_escolhido = st.selectbox(
                "Selecione o Contrato *",
                lista_contratos,
                format_func=lambda c: f"Proposta Nº {c['num_contrato']} - {c['cliente']}"
            )
            
            numero_proposta = str(contrato_escolhido['num_contrato'])
            cliente_nome = contrato_escolhido['cliente']
            email_cobranca = contrato_escolhido['email_cliente']

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("⚙️ Regras e Condições")

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                condicao = st.selectbox(
                    "Condição de Faturamento *",
                    [
                        "30 dias após inicio",
                        "Data Fixa",
                        "Penúltimo dia do mês",
                        "Fim do mês",
                        "1º dia útil do mês"
                    ]
                )
                
                dia_fixo = 10
                if condicao == "Data Fixa":
                    dia_fixo = st.number_input("Dia do mês para faturar:", min_value=1, max_value=31, value=10)

            with col_c2:
                inicio_periodo = st.date_input("Início do Período de Faturamento *", datetime.now())

            data_prevista_preview = calcular_previsao_faturamento(condicao, inicio_periodo, dia_fixo)
            st.info(f"📅 Previsão de Faturamento Calculada: **{data_prevista_preview.strftime('%d/%m/%Y')}**")

            if st.button("💾 Salvar Regra de Faturamento", key="btn_salvar_fat"):
                try:
                    novo_reg = {
                        "id_contrato": numero_proposta,
                        "cliente": cliente_nome,
                        "condicao": condicao,
                        "dia_fixo": dia_fixo,
                        "inicio_periodo": str(inicio_periodo),
                        "email_cliente": email_cobranca,
                        "status": "Ativo",
                        "alerta_enviado": 0
                    }
                    supabase.table("faturamentos").insert(novo_reg).execute()
                    st.success("Regra de faturamento guardada com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao salvar no Supabase: {e}")

    # Tela 2: Painel de Faturamentos Ativos
    elif opcao == "Painel de Faturamentos Ativos":
        st.markdown("<h1 style='text-align: center; color: #0c3547;'>💰 Painel de Faturamentos Ativos</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Acompanhe os prazos de preparação e encerre contratos quando necessário.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if "auto_fat_exec" not in st.session_state:
            msg_res = executar_automacao_faturamentos()
            st.session_state["auto_fat_exec"] = True
            if "enviado" in msg_res:
                st.toast(msg_res)

        if st.button("🔄 Executar Alertas Manualmente"):
            msg = executar_automacao_faturamentos()
            st.toast(msg)
            st.rerun()

        df = pd.DataFrame()
        try:
            response = supabase.table("faturamentos").select("*").eq("status", "Ativo").execute()
            df = pd.DataFrame(response.data)
        except Exception as e:
            st.warning("Tabela 'faturamentos' ainda não criada ou sem registos ativos.")

        if df.empty:
            st.info("Nenhum faturamento ativo no momento.")
        else:
            try:
                res_cont = supabase.table("contratos").select("id, num_contrato").execute()
                map_contratos = {str(c['id']): str(c['num_contrato']) for c in res_cont.data}
            except Exception:
                map_contratos = {}

            df['id_contrato_real'] = df['id_contrato'].apply(lambda x: map_contratos.get(str(x), str(x)))

            previsoes = []
            for _, row in df.iterrows():
                dt_prev = calcular_previsao_faturamento(
                    row['condicao'], 
                    row['inicio_periodo'], 
                    row.get('dia_fixo', 10)
                )
                previsoes.append(dt_prev.strftime('%d/%m/%Y'))
            
            df['previsao_faturamento'] = previsoes

            st.subheader("📋 Faturas e Prazos Ativos")

            display_df = df[['id_contrato_real', 'cliente', 'condicao', 'inicio_periodo', 'previsao_faturamento', 'status']].copy()
            display_df['inicio_periodo'] = pd.to_datetime(display_df['inicio_periodo']).dt.strftime('%d/%m/%Y')
            
            display_df.columns = [
                'Número da Proposta', 
                'Cliente', 
                'Condição', 
                'Início Período', 
                'Previsão de Faturamento', 
                'Status'
            ]
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("🔴 Gestão de Encerramento (Fim de Contrato)")
            st.markdown("Selecione um cliente abaixo para encerrá-lo. O registo deixará de aparecer na tela ativa e de contabilizar alertas.")

            reg_id = st.selectbox(
                "Selecionar Registo para Encerrar:",
                df['id'].tolist(),
                format_func=lambda x: f"Cliente: {df[df['id']==x]['cliente'].values[0]} (Proposta: {df[df['id']==x]['id_contrato_real'].values[0]})"
            )

            cliente_selecionado = df[df['id'] == reg_id]['cliente'].values[0]

            if st.button(f"🛑 Declarar Fim de Contrato / Encerrar ({cliente_selecionado})"):
                try:
                    supabase.table("faturamentos").update({"status": "Finalizado"}).eq("id", reg_id).execute()
                    st.success(f"Contrato/Faturamento de '{cliente_selecionado}' encerrado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao encerrar: {e}")
