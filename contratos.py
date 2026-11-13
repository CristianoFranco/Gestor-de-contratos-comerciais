import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import calendar
from supabase import create_client, Client

def executar():
    # Estilização CSS interna do módulo com as cores de alerta ajustadas
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

    if "provedor" not in st.session_state:
        st.session_state["provedor"] = config_db.get("provedor", "Outlook / Office365")
    if "email_remetente" not in st.session_state:
        st.session_state["email_remetente"] = config_db.get("email_remetente", "")
    if "senha_remetente" not in st.session_state:
        st.session_state["senha_remetente"] = config_db.get("senha_remetente", "")
    if "email_comercial_globex" not in st.session_state:
        st.session_state["email_comercial_globex"] = config_db.get("email_comercial_globex", "")

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
            return "Configure as credenciais de e-mail na aba Configuração de E-mail."

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
                dias_restantes = (data_fim - hoje).days

                # 45 dias -> Comercial Globex
                if dias_restantes <= 45 and dias_restantes > 30 and a45 == 0:
                    assunto = f"[ALERTA RENOVAÇÃO] Contrato próximo de vencer - {cliente}"
                    corpo = f"Atenção Comercial Globex,\n\nExiste um contrato próximo ao período de renovação.\n\nCliente: {cliente}\nNº Contrato: {num_contrato}\nData de Vencimento: {data_fim.strftime('%d/%m/%Y')}\nDias restantes: {dias_restantes}"
                    
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

    # Barra lateral
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

    # Tela 01: Cadastro / Edição
    if opcao == "Cadastro de Contrato":
        st.markdown("<h1 style='text-align: center; color: #0c3547;'>📝 Gestão de Cadastros de Contratos</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Cadastre novos contratos ou gerencie os registos existentes.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        tab_cad, tab_edit = st.tabs(["➕ Novo Contrato", "✏️ Editar / Excluir Contrato"])
        
        with tab_cad:
            st.subheader("Novo Contrato")
            
            col1, col2 = st.columns(2)
            with col1:
                cliente = st.text_input("Nome do Cliente *", key="nc_cliente")
                tipo_documento = st.selectbox("Tipo *", ["Proposta", "Contrato"], key="nc_tipo")
                num_contrato = st.text_input("Número da Proposta / Contrato *", key="nc_num")
                objeto_documento = st.selectbox("Objeto da Proposta / Contrato *", ["Armazenagem", "Sala"], key="nc_objeto")
                data_inicio = st.date_input("Data de Início do Contrato", datetime.now(), key="nc_inicio")
            
            with col2:
                email_cliente = st.text_input("E-mail do Cliente *", key="nc_email")
                telefone_cliente = st.text_input("Telefone do Cliente *", key="nc_tel")
                vigencia_meses = st.number_input("Vigência / Período do Reajuste (em Meses) *", min_value=1, value=12, step=1, key="nc_vig")

            total_meses = int(vigencia_meses)
            
            mes_total_inicial = data_inicio.year * 12 + (data_inicio.month - 1)
            mes_total_final = mes_total_inicial + total_meses
            
            ano_alvo = mes_total_final // 12
            mes_alvo = (mes_total_final % 12) + 1
            dia_alvo = data_inicio.day
            
            ultimo_dia_mes_alvo = calendar.monthrange(ano_alvo, mes_alvo)[1]
            if dia_alvo > ultimo_dia_mes_alvo:
                dia_alvo = ultimo_dia_mes_alvo
                
            data_fim_calculada = datetime(ano_alvo, mes_alvo, dia_alvo).date()
            data_fim_br = data_fim_calculada.strftime('%d/%m/%Y')

            st.info(f"📅 Previsão de Término / Renovação: {data_fim_br}")

            if st.button("💾 Salvar Contrato", key="btn_salvar_novo_contrato"):
                if not cliente or not num_contrato or not email_cliente:
                    st.error("Por favor, preencha todos os campos obrigatórios (*).")
                else:
                    try:
                        novo_registro = {
                            "cliente": cliente,
                            "tipo": tipo_documento,
                            "num_contrato": num_contrato,
                            "objeto": objeto_documento,
                            "data_inicio": str(data_inicio),
                            "vigencia_meses": vigencia_meses,
                            "data_fim": str(data_fim_calculada),
                            "email_cliente": email_cliente,
                            "telefone_cliente": telefone_cliente,
                            "status": "Ativo",
                            "alerta_45_enviado": 0,
                            "alerta_30_enviado": 0
                        }
                        supabase.table("contratos").insert(novo_registro).execute()
                        st.success("✅ Contrato cadastrado com sucesso!")
                        st.toast("Contrato salvo com sucesso!", icon="✅")
                    except Exception as e:
                        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                            st.error("Erro: Número de contrato já cadastrado.")
                        else:
                            st.error(f"Erro ao salvar: {e}")

        with tab_edit:
            df_edit = pd.DataFrame()
            try:
                response = supabase.table("contratos").select("*").execute()
                if response and response.data:
                    df_edit = pd.DataFrame(response.data)
                    # Ordena estritamente por ID crescente
                    if 'id' in df_edit.columns:
                        df_edit = df_edit.sort_values(by='id', ascending=True)
            except Exception as e:
                st.error(f"Erro ao carregar contratos: {e}")
            
            if df_edit.empty:
                st.info("Nenhum contrato cadastrado.")
            else:
                lista_ids = df_edit['id'].tolist()
                if "selected_contract_id" not in st.session_state or st.session_state["selected_contract_id"] not in lista_ids:
                    st.session_state["selected_contract_id"] = lista_ids[0]

                cid_edit = st.selectbox(
                    "Selecione o Contrato:",
                    lista_ids,
                    index=lista_ids.index(st.session_state["selected_contract_id"]),
                    key="select_contrato_editar",
                    format_func=lambda x: f"ID {x:02d} - {df_edit[df_edit['id']==x]['cliente'].values[0]} ({df_edit[df_edit['id']==x]['num_contrato'].values[0]})"
                )
                
                st.session_state["selected_contract_id"] = cid_edit
                c_data = df_edit[df_edit['id'] == cid_edit].iloc[0]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Nome do Cliente (Fixo)", value=c_data['cliente'], disabled=True, key=f"edit_cliente_{cid_edit}")
                    
                    tipo_atual = c_data.get('tipo', 'Contrato')
                    idx_tipo = 0 if tipo_atual == "Proposta" else 1
                    novo_tipo = st.selectbox("Tipo *", ["Proposta", "Contrato"], index=idx_tipo, key=f"edit_tipo_{cid_edit}")
                    
                    st.text_input("Número da Proposta / Contrato (Fixo)", value=c_data['num_contrato'], disabled=True, key=f"edit_num_{cid_edit}")
                    
                    objeto_atual = c_data.get('objeto', 'Armazenagem')
                    idx_obj = 1 if objeto_atual == "Sala" else 0
                    novo_objeto = st.selectbox("Objeto da Proposta / Contrato *", ["Armazenagem", "Sala"], index=idx_obj, key=f"edit_objeto_{cid_edit}")
                    
                    data_inicio_edit = st.date_input("Data de Início", value=datetime.strptime(c_data['data_inicio'], "%Y-%m-%d").date(), key=f"edit_data_{cid_edit}")
                with col2:
                    novo_email = st.text_input("E-mail do Cliente *", value=c_data['email_cliente'], key=f"edit_email_{cid_edit}")
                    novo_tel = st.text_input("Telefone do Cliente *", value=c_data['telefone_cliente'], key=f"edit_tel_{cid_edit}")
                    nova_vigencia = st.number_input("Vigência (Meses) *", min_value=1, value=int(c_data['vigencia_meses']), step=1, key=f"edit_vig_{cid_edit}")
                
                t_meses = int(nova_vigencia)
                
                mes_total_ini_ed = data_inicio_edit.year * 12 + (data_inicio_edit.month - 1)
                mes_total_fim_ed = mes_total_ini_ed + t_meses
                
                a_alvo = mes_total_fim_ed // 12
                m_alvo = (mes_total_fim_ed % 12) + 1
                d_alvo = data_inicio_edit.day
                
                ultimo_d = calendar.monthrange(a_alvo, m_alvo)[1]
                if d_alvo > ultimo_d:
                    d_alvo = ultimo_d
                nova_data_fim = datetime(a_alvo, m_alvo, d_alvo).date()

                st.info(f"📅 Nova Data Fim Recalculada pela Vigência: {nova_data_fim.strftime('%d/%m/%Y')}")
                
                forcar_data_fim = st.checkbox("Definir Data Limite de Vigência Manualmente (Término Antecipado / Rescisão)", key=f"chk_forcar_{cid_edit}")
                if forcar_data_fim:
                    dt_atual_fim = datetime.strptime(c_data['data_fim'], "%Y-%m-%d").date() if c_data.get('data_fim') else nova_data_fim
                    nova_data_fim = st.date_input("Nova Data Final de Vigência *", value=dt_atual_fim, key=f"input_nova_fim_{cid_edit}")
                    st.warning(f"⚠️ A data limite do contrato foi fixada manualmente em: **{nova_data_fim.strftime('%d/%m/%Y')}**. O faturamento respeitará este limite.")

                if st.button("💾 Salvar Alterações", key=f"btn_salvar_edit_{cid_edit}"):
                    if not novo_email:
                        st.error("Preencha o e-mail do cliente obrigatório (*).")
                    else:
                        try:
                            dados_atualizados = {
                                "cliente": c_data['cliente'],
                                "tipo": novo_tipo,
                                "num_contrato": c_data['num_contrato'],
                                "objeto": novo_objeto,
                                "data_inicio": str(data_inicio_edit),
                                "vigencia_meses": nova_vigencia,
                                "data_fim": str(nova_data_fim),
                                "email_cliente": novo_email,
                                "telefone_cliente": novo_tel
                            }
                            supabase.table("contratos").update(dados_atualizados).eq("id", cid_edit).execute()
                            
                            if "selected_contract_id" in st.session_state:
                                del st.session_state["selected_contract_id"]
                                
                            st.success("✅ Contrato atualizado com sucesso!")
                            st.toast("Alterações salvas com sucesso!", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar: {e}")

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("---")
                st.subheader("⚠️ Zona de Exclusão")
                
                if st.button("🗑️ Excluir Contrato Permanentemente", key=f"btn_excluir_{cid_edit}"):
                    try:
                        supabase.table("contratos").delete().eq("id", cid_edit).execute()
                        if "selected_contract_id" in st.session_state:
                            del st.session_state["selected_contract_id"]
                        
                        st.success("✅ Contrato excluído permanentemente!")
                        st.toast("Contrato excluído!", icon="🗑️")
                        st.rerun()
                    except Exception as e:
                        st.error("🚫 **Operação Bloqueada:** Não foi possível excluir o contrato devido a haver faturamentos programados na base de dados.")

    # Tela 02: Painel de Gestão e Ações
    elif opcao == "Gestão de Contratos":
        st.markdown("<h1 style='text-align: center; color: #0c3547;'>📊 Painel de Gestão de Contratos</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Acompanhe os prazos de vigência, status e gerencie renovações ou encerramentos.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if "automacao_executada" not in st.session_state:
            msg_auto = executar_automacao_alertas()
            st.session_state["automacao_executada"] = True
            if "com sucesso" in msg_auto:
                st.toast(msg_auto)

        col_btn1, col_btn2 = st.columns([1, 3])
        with col_btn1:
            if st.button("🔄 Executar Alertas Manualmente"):
                msg_res = executar_automacao_alertas()
                st.toast(msg_res)
                st.rerun()

        df = pd.DataFrame()
        try:
            response = supabase.table("contratos").select("*").execute()
            if response and response.data:
                df = pd.DataFrame(response.data)
        except Exception as e:
            st.error(f"Erro ao carregar dados do Supabase: {e}")

        if df.empty:
            st.warning("Nenhum contrato cadastrado.")
        else:
            hoje = datetime.now().date()
            df['data_fim_dt'] = pd.to_datetime(df['data_fim']).dt.date
            df['dias_restantes'] = df['data_fim_dt'].apply(lambda x: (x - hoje).days)
            
            df = df.sort_values(by='dias_restantes', ascending=True)

            total_contratos = len(df)
            vencidos_df = df[df['dias_restantes'] < 0]
            vencendo_breve = len(df[(df['dias_restantes'] >= 0) & (df['dias_restantes'] <= 45)])
            
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
                        <h3 style="margin:0; color:#d90429;">{vencendo_breve + len(vencidos_df)}</h3>
                        <p style="margin:0; color:#666;">Vencendo em breve / Vencidos (≤ 45 dias)</p>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📋 Lista Geral de Contratos")
            
            if not vencidos_df.empty:
                st.error(f"🚨 Atenção: Existem **{len(vencidos_df)}** contrato(s) com prazo de vigência vencido destacados em vermelho!")

            # Garante colunas opcionais caso existam registos antigos sem elas
            for col_nec in ['tipo', 'objeto']:
                if col_nec not in df.columns:
                    df[col_nec] = 'Contrato' if col_nec == 'tipo' else 'Armazenagem'

            display_df = df[['id', 'cliente', 'tipo', 'num_contrato', 'objeto', 'data_inicio', 'vigencia_meses', 'data_fim', 'dias_restantes', 'status']].copy()
            display_df['data_inicio'] = pd.to_datetime(display_df['data_inicio']).dt.strftime('%d/%m/%Y')
            display_df['data_fim'] = pd.to_datetime(display_df['data_fim']).dt.strftime('%d/%m/%Y')
            display_df.columns = ['ID', 'Cliente', 'Tipo', 'Nº Proposta/Contrato', 'Objeto', 'Início', 'Vigência (Meses)', 'Vencimento', 'Dias p/ Vencer', 'Status Atual']
            
            # Função de estilização (Vermelho se vencido < 0, Amarelo se entre 0 e 45 dias)
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
                "Selecione o Contrato para Gerir:",
                df['id'].tolist(),
                format_func=lambda x: f"ID {x:02d} - {df[df['id']==x]['cliente'].values[0]} ({df[df['id']==x]['num_contrato'].values[0]})"
            )
            
            contrato_atual = df[df['id'] == contrato_id].iloc[0]
            vencimento_br = datetime.strptime(str(contrato_atual['data_fim']), "%Y-%m-%d").strftime("%d/%m/%Y")

            if contrato_atual['dias_restantes'] < 0:
                dias_atraso = abs(contrato_atual['dias_restantes'])
                st.error(f"🚨 **CONTRATO VENCIDO!** | Cliente: {contrato_atual['cliente']} | Status: `{contrato_atual['status']}` | Vencimento: {vencimento_br} ({dias_atraso} dias atrás)")
            else:
                st.info(f"Cliente: {contrato_atual['cliente']} | Status: `{contrato_atual['status']}` | Vencimento: {vencimento_br}")

            opcoes_status = [
                "Ativo",
                "Informado ao comercial por email",
                "Informado ao cliente por email",
                "Em negociação com o cliente",
                "Renegociado"
            ]
            
            idx_def = opcoes_status.index(contrato_atual['status']) if contrato_atual['status'] in opcoes_status else 0
            novo_status = st.selectbox("Novo Status:", opcoes_status, index=idx_def)

            if novo_status == "Renegociado":
                st.warning("🔄 Ao renegociar, o contrato será renovado para o próximo ciclo.")
                
                tipo_reajuste = st.radio("Reajuste:", ["Manter Vigência em Meses", "Ajustar Data Fim Manualmente"])
                
                nova_data_inicio = datetime.now().date()
                if tipo_reajuste == "Manter Vigência em Meses":
                    novos_meses = st.number_input("Nova Vigência (meses)", min_value=1, value=int(contrato_atual['vigencia_meses']))
                    t_m = int(novos_meses)
                    
                    mes_tot_ren = nova_data_inicio.year * 12 + (nova_data_inicio.month - 1) + t_m
                    a_a = mes_tot_ren // 12
                    m_a = (mes_tot_ren % 12) + 1
                    d_a = nova_data_inicio.day
                    ultimo_d_a = calendar.monthrange(a_
