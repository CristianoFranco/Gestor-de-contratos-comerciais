import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import calendar

def carregar_config_email_faturamento(supabase):
    try:
        res = supabase.table("config_email_faturamento").select("*").eq("id", 1).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {}

def enviar_email_para_todos(provedor, email_remetente, senha, lista_destinos, assunto, mensagem, cliente, proposta, supabase):
    sucessos = 0
    erros = []
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

        for destino in lista_destinos:
            destino = destino.strip()
            if not destino:
                continue
            try:
                msg = MIMEMultipart()
                msg['From'] = email_remetente
                msg['To'] = destino
                msg['Subject'] = assunto
                msg.attach(MIMEText(mensagem, 'plain'))
                server.send_message(msg)
                sucessos += 1
            except Exception as ex:
                erros.append(f"{destino}: {ex}")

        server.quit()

        if sucessos > 0:
            try:
                log_data = {
                    "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "cliente": cliente,
                    "proposta": str(proposta),
                    "mensagem": f"Assunto: {assunto}\n\n{mensagem}",
                    "status": f"Enviado com sucesso para {sucessos} destinatário(s)"
                }
                supabase.table("logs_faturamento").insert(log_data).execute()
            except Exception:
                pass
            return True, f"E-mail enviado com sucesso para {sucessos} destinatário(s)!"
        return False, f"Falha ao enviar. Erros: {erros}"
    except Exception as e:
        return False, str(e)

def ajustar_dia_util(data_obj, direcao="retroceder"):
    while data_obj.weekday() >= 5:  # Sábado (5) ou Domingo (6)
        if direcao == "retroceder":
            data_obj -= timedelta(days=1)
        else:
            data_obj += timedelta(days=1)
    return data_obj

def calcular_previsao_faturamento(condicao, inicio_dt, dia_fixo=10, pular_mes_atual=False):
    if isinstance(inicio_dt, str):
        inicio_dt = datetime.strptime(inicio_dt, "%Y-%m-%d").date()

    base_dt = inicio_dt
    if pular_mes_atual:
        mes_seguinte = inicio_dt.month % 12 + 1
        ano_seguinte = inicio_dt.year + (1 if inicio_dt.month == 12 else 0)
        base_dt = datetime(ano_seguinte, mes_seguinte, min(inicio_dt.day, calendar.monthrange(ano_seguinte, mes_seguinte)[1])).date()

    if condicao == "30 dias após inicio":
        data_fatura = base_dt + timedelta(days=30)
        data_fatura = ajustar_dia_util(data_fatura, "avancar")
    
    elif condicao == "Data Fixa":
        d_fixo = min(int(dia_fixo), calendar.monthrange(base_dt.year, base_dt.month)[1])
        data_fatura = datetime(base_dt.year, base_dt.month, d_fixo).date()
        if data_fatura < base_dt:
            mes_prox = base_dt.month % 12 + 1
            ano_prox = base_dt.year + (1 if base_dt.month == 12 else 0)
            d_fixo_prox = min(int(dia_fixo), calendar.monthrange(ano_prox, mes_prox)[1])
            data_fatura = datetime(ano_prox, mes_prox, d_fixo_prox).date()
        data_fatura = ajustar_dia_util(data_fatura, "retroceder")
    
    elif condicao == "1º dia útil do mês":
        primeiro_dia = datetime(base_dt.year, base_dt.month, 1).date()
        data_fatura = ajustar_dia_util(primeiro_dia, "avancar")
        if not pular_mes_atual and base_dt > data_fatura:
            mes_prox = base_dt.month % 12 + 1
            ano_prox = base_dt.year + (1 if base_dt.month == 12 else 0)
            primeiro_dia_prox = datetime(ano_prox, mes_prox, 1).date()
            data_fatura = ajustar_dia_util(primeiro_dia_prox, "avancar")
    
    elif condicao == "Penúltimo dia do mês":
        ultimo_dia_num = calendar.monthrange(base_dt.year, base_dt.month)[1]
        penultimo_dia = datetime(base_dt.year, base_dt.month, ultimo_dia_num - 1).date()
        data_fatura = ajustar_dia_util(penultimo_dia, "retroceder")
        if not pular_mes_atual and base_dt > data_fatura:
            mes_prox = base_dt.month % 12 + 1
            ano_prox = base_dt.year + (1 if base_dt.month == 12 else 0)
            ultimo_dia_prox = calendar.monthrange(ano_prox, mes_prox)[1]
            penultimo_prox = datetime(ano_prox, mes_prox, ultimo_dia_prox - 1).date()
            data_fatura = ajustar_dia_util(penultimo_prox, "retroceder")
    
    elif condicao == "Fim do mês":
        ultimo_dia_num = calendar.monthrange(base_dt.year, base_dt.month)[1]
        ultimo_dia = datetime(base_dt.year, base_dt.month, ultimo_dia_num).date()
        data_fatura = ajustar_dia_util(ultimo_dia, "retroceder")
        if not pular_mes_atual and base_dt > data_fatura:
            mes_prox = base_dt.month % 12 + 1
            ano_prox = base_dt.year + (1 if base_dt.month == 12 else 0)
            ultimo_dia_prox = calendar.monthrange(ano_prox, mes_prox)[1]
            ultimo_prox = datetime(ano_prox, mes_prox, ultimo_dia_prox).date()
            data_fatura = ajustar_dia_util(ultimo_prox, "retroceder")
    
    else:
        data_fatura = base_dt
    return data_fatura

def executar_automacao_faturamentos(supabase, config_db):
    remetente = st.session_state.get("fat_email_remetente") or config_db.get("email_remetente")
    senha = st.session_state.get("fat_senha_remetente") or config_db.get("senha_remetente")
    prov = st.session_state.get("fat_provedor") or config_db.get("provedor", "Outlook / Office365")
    destinos_str = st.session_state.get("fat_emails_destino") or config_db.get("emails_destino", "")

    if not remetente or not senha or not destinos_str:
        return "Configure as credenciais e os e-mails de destino na aba 'Configurações de E-mail'."

    lista_destinos = [e.strip() for e in destinos_str.replace(";", ",").split(",") if e.strip()]
    if not lista_destinos:
        return "Nenhum e-mail de destino configurado."

    try:
        response = supabase.table("faturamentos").select("*").eq("status", "Ativo").execute()
        registros = response.data if response and response.data else []

        hoje = datetime.now().date()
        disparos = 0

        for item in registros:
            rid = item['id']
            cliente = item['cliente']
            num_prop = item['id_contrato']
            condicao = item['condicao']
            inicio_str = item['inicio_periodo']
            alerta_enviado = item.get('alerta_enviado', 0)
            dia_fixo = item.get('dia_fixo', 10)
            pular_mes = item.get('pular_mes_atual', False)

            inicio_dt = datetime.strptime(inicio_str, "%Y-%m-%d").date()
            data_fatura = calcular_previsao_faturamento(condicao, inicio_dt, dia_fixo, pular_mes)

            dias_restantes = (data_fatura - hoje).days

            if dias_restantes == 2 and alerta_enviado < 1:
                assunto = f"[ALERTA OPERACIONAL] Preparação de Faturamento - Proposta Nº {num_prop} ({cliente})"
                corpo = f"Atenção Equipa,\n\nO faturamento para o cliente {cliente} (Proposta Nº {num_prop}, Condição: {condicao}) tem data prevista para {data_fatura.strftime('%d/%m/%Y')}.\nFaltam 2 dias para a data limite de preparação de dados.\n\nAtenciosamente,\nGlobex Multimodal"
                
                sucesso, err = enviar_email_para_todos(prov, remetente, senha, lista_destinos, assunto, corpo, cliente, num_prop, supabase)
                if sucesso:
                    supabase.table("faturamentos").update({"alerta_enviado": 1}).eq("id", rid).execute()
                    disparos += 1

            elif dias_restantes == 1 and alerta_enviado < 2:
                assunto = f"[ALERTA OPERACIONAL] Véspera de Faturamento - Proposta Nº {num_prop} ({cliente})"
                corpo = f"Atenção Equipa,\n\nO faturamento para o cliente {cliente} (Proposta Nº {num_prop}, Condição: {condicao}) tem data prevista para AMANHÃ ({data_fatura.strftime('%d/%m/%Y')}).\nCertifiquem-se de que os dados estão prontos.\n\nAtenciosamente,\nGlobex Multimodal"
                
                sucesso, err = enviar_email_para_todos(prov, remetente, senha, lista_destinos, assunto, corpo, cliente, num_prop, supabase)
                if sucesso:
                    supabase.table("faturamentos").update({"alerta_enviado": 2}).eq("id", rid).execute()
                    disparos += 1

            elif dias_restantes == 0 and alerta_enviado < 3:
                assunto = f"[URGENTE - HOJE] Prazo de Faturamento - Proposta Nº {num_prop} ({cliente})"
                corpo = f"Atenção Equipa,\n\nO faturamento para o cliente {cliente} (Proposta Nº {num_prop}, Condição: {condicao}) tem o prazo de entrega PARA HOJE ({data_fatura.strftime('%d/%m/%Y')}).\n\nO faturamento está finalizado ou a ser finalizado? Por favor, verifiquem com urgência.\n\nAtenciosamente,\nGlobex Multimodal"
                
                sucesso, err = enviar_email_para_todos(prov, remetente, senha, lista_destinos, assunto, corpo, cliente, num_prop, supabase)
                if sucesso:
                    supabase.table("faturamentos").update({"alerta_enviado": 3}).eq("id", rid).execute()
                    disparos += 1

        if disparos > 0:
            return f"Automação executada! {disparos} alerta(s) operacional(is) disparado(s) para a equipa."
        return "Nenhum alerta de faturamento pendente para hoje."
    except Exception as e:
        return f"Erro na automação: {e}"

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

    config_db = carregar_config_email_faturamento(supabase)

    if "fat_provedor" not in st.session_state:
        st.session_state["fat_provedor"] = config_db.get("provedor", "Outlook / Office365")
    if "fat_email_remetente" not in st.session_state:
        st.session_state["fat_email_remetente"] = config_db.get("email_remetente", "")
    if "fat_senha_remetente" not in st.session_state:
        st.session_state["fat_senha_remetente"] = config_db.get("senha_remetente", "")
    if "fat_emails_destino" not in st.session_state:
        st.session_state["fat_emails_destino"] = config_db.get("emails_destino", "")

    with st.sidebar:
        caminho_logo_side = "Logo.png" if os.path.exists("Logo.png") else ("logo.png" if os.path.exists("logo.png") else None)
        if caminho_logo_side:
            st.image(caminho_logo_side, use_container_width=True)
        else:
            st.markdown("### 🌐 GLOBEX MULTIMODAL")
        
        st.markdown("---")
        menu = ["Novo / Editar Faturamento", "Painel de Faturamentos Ativos", "Configurações de E-mail", "Gerenciar Logs de Mensagens"]
        opcao = st.radio("Navegação Faturamentos", menu)
        st.markdown("---")
        st.caption("© 2026 Globex Multimodal")

    if opcao == "Novo / Editar Faturamento":
        st.markdown("<h1 style='text-align: center; color: #0c3547;'>📝 Gestão de Regras de Faturamento</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Cadastre novos faturamentos (via Contratos ou Manual Avulso) ou edite lançamentos existentes.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        modo = st.radio("Modo de Operação:", ["Novo Faturamento", "Cadastro Manual (Avulso)", "Editar Faturamento Existente"], horizontal=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if modo == "Novo Faturamento":
            try:
                res_contratos = supabase.table("contratos").select("*").execute()
                lista_contratos = res_contratos.data if res_contratos and res_contratos.data else []
            except Exception:
                lista_contratos = []

            propostas_ja_cadastradas = []
            try:
                res_fat_todos = supabase.table("faturamentos").select("id_contrato").execute()
                if res_fat_todos and res_fat_todos.data:
                    propostas_ja_cadastradas = [str(item['id_contrato']) for item in res_fat_todos.data]
            except Exception:
                pass

            contratos_disponiveis = [
                c for c in lista_contratos 
                if str(c['num_contrato']) not in propostas_ja_cadastradas and str(c['id']) not in propostas_ja_cadastradas
            ]

            if not lista_contratos:
                st.warning("⚠️ Nenhum contrato encontrado na base de dados. Utilize o 'Cadastro Manual (Avulso)' ao lado.")
            elif not contratos_disponiveis:
                st.info("💡 Todos os contratos já possuem faturamento configurado ou foram ignorados. Utilize o 'Cadastro Manual (Avulso)' para novos lançamentos.")
            else:
                col_sel1, col_sel2 = st.columns([3, 1])
                with col_sel1:
                    contrato_escolhido = st.selectbox(
                        "Selecione o Contrato *",
                        contratos_disponiveis,
                        format_func=lambda c: f"Proposta Nº {c['num_contrato']} - {c['cliente']}"
                    )
                with col_sel2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ Ignorar Contrato", key="btn_ignorar_contrato"):
                        try:
                            reg_ignorado = {
                                "id_contrato": str(contrato_escolhido['num_contrato']),
                                "cliente": contrato_escolhido['cliente'],
                                "condicao": "Fim do mês",
                                "inicio_periodo": str(datetime.now().date()),
                                "status": "Ignorado",
                                "alerta_enviado": 0,
                                "pular_mes_atual": False
                            }
                            supabase.table("faturamentos").insert(reg_ignorado).execute()
                            st.success(f"Proposta Nº {contrato_escolhido['num_contrato']} ignorada da fila!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao ignorar contrato: {e}")
                
                numero_proposta = str(contrato_escolhido['num_contrato'])
                cliente_nome = contrato_escolhido['cliente']
                email_cobranca = contrato_escolhido.get('email_cliente', '')

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
                    pular_mes_atual = st.checkbox("Pular faturamento do mês atual (começar a partir do mês seguinte)", key="pular_novo")

                data_prevista_preview = calcular_previsao_faturamento(condicao, inicio_periodo, dia_fixo, pular_mes_atual)
                st.info(f"📅 Previsão de Faturamento Calculada: **{data_prevista_preview.strftime('%d/%m/%Y')}**")

                if st.button("💾 Salvar Regra de Faturamento", key="btn_salvar_fat"):
                    try:
                        res_dup = supabase.table("faturamentos").select("id_contrato").eq("id_contrato", numero_proposta).execute()
                        ja_existe = res_dup.data if res_dup and res_dup.data else []
                    except Exception:
                        ja_existe = []

                    if ja_existe:
                        st.error(f"❌ Erro: Já existe um faturamento registado com o número de proposta '{numero_proposta}'. Proibido duplicar propostas!")
                    else:
                        try:
                            novo_reg = {
                                "id_contrato": numero_proposta,
                                "cliente": cliente_nome,
                                "condicao": condicao,
                                "dia_fixo": dia_fixo,
                                "inicio_periodo": str(inicio_periodo),
                                "email_cliente": email_cobranca,
                                "status": "Ativo",
                                "alerta_enviado": 0,
                                "pular_mes_atual": pular_mes_atual
                            }
                            supabase.table("faturamentos").insert(novo_reg).execute()
                            st.success("Regra de faturamento guardada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar no Supabase: {e}")

        elif modo == "Cadastro Manual (Avulso)":
            st.markdown("### ✍️ Inserção Manual de Contrato / Proposta")
            st.markdown("<p style='color: #666;'>Preencha os campos abaixo livremente. Este registo ficará exclusivo no Gestor de Faturamentos.</p>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                numero_proposta = st.text_input("Número da Proposta / Contrato *", placeholder="Ex: PROP-2026-99")
            with col_m2:
                cliente_nome = st.text_input("Nome do Cliente *", placeholder="Nome da Empresa")

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("⚙️ Regras e Condições")

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                condicao_man = st.selectbox(
                    "Condição de Faturamento *",
                    [
                        "30 dias após inicio",
                        "Data Fixa",
                        "Penúltimo dia do mês",
                        "Fim do mês",
                        "1º dia útil do mês"
                    ],
                    key="cond_man"
                )
                
                dia_fixo_man = 10
                if condicao_man == "Data Fixa":
                    dia_fixo_man = st.number_input("Dia do mês para faturar:", min_value=1, max_value=31, value=10, key="dia_fixo_man")

            with col_c2:
                inicio_periodo_man = st.date_input("Início do Período de Faturamento *", datetime.now(), key="inicio_man")
                pular_mes_man = st.checkbox("Pular faturamento do mês atual (começar a partir do mês seguinte)", key="pular_man_avulso")

            data_prevista_preview_man = calcular_previsao_faturamento(condicao_man, inicio_periodo_man, dia_fixo_man, pular_mes_man)
            st.info(f"📅 Previsão de Faturamento Calculada: **{data_prevista_preview_man.strftime('%d/%m/%Y')}**")

            if st.button("💾 Salvar Regra de Faturamento Manual", key="btn_salvar_fat_manual"):
                if not numero_proposta or not cliente_nome:
                    st.error("Por favor, preencha todos os campos obrigatórios (*).")
                else:
                    try:
                        res_dup_man = supabase.table("faturamentos").select("id_contrato").eq("id_contrato", str(numero_proposta).strip()).execute()
                        ja_existe_man = res_dup_man.data if res_dup_man and res_dup_man.data else []
                    except Exception:
                        ja_existe_man = []

                    if ja_existe_man:
                        st.error(f"❌ Erro: Já existe um faturamento registado com o número de proposta '{numero_proposta}'. O sistema não permite números de propostas duplicados!")
                    else:
                        try:
                            novo_reg_manual = {
                                "id_contrato": str(numero_proposta).strip(),
                                "cliente": cliente_nome,
                                "condicao": condicao_man,
                                "dia_fixo": dia_fixo_man,
                                "inicio_periodo": str(inicio_periodo_man),
                                "email_cliente": "",
                                "status": "Ativo",
                                "alerta_enviado": 0,
                                "pular_mes_atual": pular_mes_man
                            }
                            supabase.table("faturamentos").insert(novo_reg_manual).execute()
                            st.success(f"Regra manual para '{cliente_nome}' guardada com sucesso na Gestão de Faturamentos!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar no Supabase: {e}")

        else:
            df_ativos = pd.DataFrame()
            try:
                res_ativos = supabase.table("faturamentos").select("*").eq("status", "Ativo").execute()
                if res_ativos and res_ativos.data:
                    df_ativos = pd.DataFrame(res_ativos.data)
            except Exception:
                pass

            if df_ativos.empty:
                st.info("Nenhum faturamento ativo disponível para edição.")
            else:
                fat_selecionado_id = st.selectbox(
                    "Selecione o Faturamento Ativo para Editar:",
                    df_ativos['id'].tolist(),
                    format_func=lambda x: f"Proposta Nº {df_ativos[df_ativos['id']==x]['id_contrato'].values[0]} - {df_ativos[df_ativos['id']==x]['cliente'].values[0]}"
                )

                reg_atual = df_ativos[df_ativos['id'] == fat_selecionado_id].iloc[0]

                st.markdown(f"**Cliente:** {reg_atual['cliente']} | **Proposta Nº:** {reg_atual['id_contrato']}")
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("⚙️ Atualizar Regras e Condições")

                condicoes_lista = [
                    "30 dias após inicio",
                    "Data Fixa",
                    "Penúltimo dia do mês",
                    "Fim do mês",
                    "1º dia útil do mês"
                ]
                idx_cond = condicoes_lista.index(reg_atual['condicao']) if reg_atual['condicao'] in condicoes_lista else 0

                col_e1, col_
