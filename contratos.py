import streamlit as st
import pandas as pd
from datetime import datetime
import re

def normalizar_categoria_item(cat_str):
    """Normaliza as categorias antigas da migração ou variações para o padrão atual do sistema."""
    cat_limpa = str(cat_str).strip().lower()
    if "armazenagem" in cat_limpa:
        return "Armazenagem"
    elif "seguro" in cat_limpa:
        return "Seguro"
    elif "movimentacao" in cat_limpa or "handling" in cat_limpa or "servicos e movimentacoes" in cat_limpa or "serviço" in cat_limpa:
        return "Serviço"
    elif "conex" in cat_limpa or "outros" in cat_limpa:
        return "Serviços Conexos"
    else:
        return "Serviço"

def renderizar_aba_propostas(carregar_dados_fn, salvar_dados_completos_fn, obter_proximo_numero_fn):
    st.markdown("""
        <style>
            div[data-testid="stTextInput"] label,
            div[data-testid="stSelectbox"] label,
            div[data-testid="stNumberInput"] label,
            div[data-testid="stTextArea"] label,
            div[data-testid="stTextInput"] label p,
            div[data-testid="stSelectbox"] label p,
            div[data-testid="stNumberInput"] label p,
            div[data-testid="stTextArea"] label p {
                color: #2E86DE !important;
                font-weight: bold !important;
                font-size: 15px !important;
            }
            div[data-testid="stDataFrame"] {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("## 🛠️ Gestão de Proposta Rascunho")
    st.caption("Monte, edite e envie propostas comerciais para os clientes de forma integrada.")
    st.markdown("<br>", unsafe_allow_html=True)

    # Inicialização de estados
    if "itens_proposta_rascunho" not in st.session_state:
        st.session_state["itens_proposta_rascunho"] = []
    if "proposta_id_em_edicao" not in st.session_state:
        st.session_state["proposta_id_em_edicao"] = None
    if "cliente_proposta" not in st.session_state:
        st.session_state["cliente_proposta"] = ""
    if "cnpj_proposta" not in st.session_state:
        st.session_state["cnpj_proposta"] = ""

    # Carrega dados de serviços ativos
    try:
        df_servicos = carregar_dados_fn(apenas_ativos=True)
    except Exception:
        df_servicos = pd.DataFrame()

    if df_servicos is None or df_servicos.empty:
        st.warning("⚠️ Nenhum serviço ativo encontrado na base de dados. Cadastre serviços na aba 'Cadastro' primeiro.")
        return

    # Garante colunas essenciais
    colunas_serv = ["Código", "Descrição", "Tarifa (R$)", "Unidade", "Categoria", "Observações"]
    for col in colunas_serv:
        if col not in df_servicos.columns:
            df_servicos[col] = ""

    # ==========================================================================
    # CARREGAR PROPOSTA EXISTENTE PARA EDIÇÃO
    # ==========================================================================
    st.markdown("### 📂 Carregar Proposta Existente para Edição")
    try:
        from __main__ import carregar_propostas_do_supabase
        df_propostas_salvas = carregar_propostas_do_supabase()
    except Exception:
        df_propostas_salvas = pd.DataFrame()

    if not df_propostas_salvas.empty and "Proposta" in df_propostas_salvas.columns:
        lista_propostas_existentes = [""] + sorted(df_propostas_salvas["Proposta"].dropna().unique().tolist())
        prop_selecionada = st.selectbox("Selecione o Número da Proposta para Carregar:", options=lista_propostas_existentes, key="select_prop_carregar_edicao")
        
        if prop_selecionada:
            if st.button("📥 Carregar Dados da Proposta", key="btn_carregar_dados_prop"):
                df_filtrado = df_propostas_salvas[df_propostas_salvas["Proposta"] == prop_selecionada].copy()
                
                # Remove duplicidades idênticas geradas em migrações anteriores
                df_filtrado = df_filtrado.drop_duplicates(subset=["Proposta", "Código", "Descrição", "Tarifa (R$)"])
                
                if not df_filtrado.empty:
                    st.session_state["proposta_id_em_edicao"] = prop_selecionada
                    st.session_state["cliente_proposta"] = str(df_filtrado.iloc[0].get("Cliente", ""))
                    st.session_state["cnpj_proposta"] = str(df_filtrado.get("CNPJ", "").iloc[0]) if "CNPJ" in df_filtrado.columns else ""
                    
                    novos_itens = []
                    for _, row in df_filtrado.iterrows():
                        cat_normalizada = normalizar_categoria_item(row.get("Categoria", ""))
                        novos_itens.append({
                            "Código": str(row.get("Código", "")).strip(),
                            "Descrição": str(row.get("Descrição", "")).strip(),
                            "Categoria": cat_normalizada,
                            "Unidade": str(row.get("Unidade", "")).strip(),
                            "Tarifa (R$)": float(row.get("Tarifa (R$)", 0.0) if str(row.get("Tarifa (R$)", 0.0)).strip() != "" else 0.0),
                            "Observações": str(row.get("Observações", "")).strip()
                        })
                    st.session_state["itens_proposta_rascunho"] = novos_itens
                    st.success(f"Proposta '{prop_selecionada}' carregada com sucesso para edição!")
                    st.rerun()

    st.markdown("---")

    # ==========================================================================
    # DADOS DO CLIENTE E IDENTIFICAÇÃO DA PROPOSTA
    # ==========================================================================
    st.markdown("### 🏢 Informações do Cliente")
    col_inf1, col_inf2, col_inf3 = st.columns([1.5, 1.5, 1])

    with col_inf1:
        cliente_input = st.text_input("Nome do Cliente *", value=st.session_state.get("cliente_proposta", ""), key="input_cliente_prop")
        st.session_state["cliente_proposta"] = cliente_input

    with col_inf2:
        cnpj_input = st.text_input("CNPJ do Cliente", value=st.session_state.get("cnpj_proposta", ""), key="input_cnpj_prop")
        st.session_state["cnpj_proposta"] = cnpj_input

    with col_inf3:
        num_proposta_atual = obter_proximo_numero_fn()
        st.text_input("Nº da Proposta", value=num_proposta_atual, disabled=True, key="input_num_prop_display")

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================================================
    # ADICIONAR ITENS POR CATEGORIA
    # ==========================================================================
    st.markdown("### ➕ Seleção e Inclusão de Serviços")

    # Separação dos serviços disponíveis baseando-se na normalização
    df_servicos["Categoria_Norm"] = df_servicos["Categoria"].apply(normalizar_categoria_item)
    
    codigos_ja_adicionados = [str(item["Código"]) for item in st.session_state["itens_proposta_rascunho"]]

    # 1. ARMAZENAGEM
    st.markdown("#### 📦 Armazenagem")
    df_arm = df_servicos[df_servicos["Categoria_Norm"] == "Armazenagem"]
    df_arm_disp = df_arm[~df_arm["Código"].isin(codigos_ja_adicionados)]

    if df_arm_disp.empty:
        st.info("Nenhum serviço de Armazenagem disponível para adicionar.")
    else:
        col_arm1, col_arm2 = st.columns([3, 1])
        with col_arm1:
            opcoes_arm = {f"{r['Código']} - {r['Descrição']}": r['Código'] for _, r in df_arm_disp.iterrows()}
            escolha_arm = st.selectbox("Selecionar Armazenagem:", options=[""] + list(opcoes_arm.keys()), key="select_arm_prop")
        with col_arm2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Adicionar Armazenagem", key="btn_add_arm", use_container_width=True):
                if escolha_arm:
                    cod_escolhido = opcoes_arm[escolha_arm]
                    row_serv = df_servicos[df_servicos["Código"] == cod_escolhido].iloc[0]
                    st.session_state["itens_proposta_rascunho"].append({
                        "Código": str(row_serv["Código"]),
                        "Descrição": str(row_serv["Descrição"]),
                        "Categoria": "Armazenagem",
                        "Unidade": str(row_serv["Unidade"]),
                        "Tarifa (R$)": float(row_serv["Tarifa (R$)"]),
                        "Observações": str(row_serv["Observações"]) if pd.notna(row_serv["Observações"]) else ""
                    })
                    st.rerun()

    # 2. SEGURO
    st.markdown("#### 🛡️ Seguro")
    df_seg = df_servicos[df_servicos["Categoria_Norm"] == "Seguro"]
    df_seg_disp = df_seg[~df_seg["Código"].isin(codigos_ja_adicionados)]

    if df_seg_disp.empty:
        st.info("Nenhum serviço de Seguro disponível para adicionar.")
    else:
        col_seg1, col_seg2 = st.columns([3, 1])
        with col_seg1:
            opcoes_seg = {f"{r['Código']} - {r['Descrição']}": r['Código'] for _, r in df_seg_disp.iterrows()}
            escolha_seg = st.selectbox("Selecionar Seguro:", options=[""] + list(opcoes_seg.keys()), key="select_seg_prop")
        with col_seg2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Adicionar Seguro", key="btn_add_seg", use_container_width=True):
                if escolha_seg:
                    cod_escolhido = opcoes_seg[escolha_seg]
                    row_serv = df_servicos[df_servicos["Código"] == cod_escolhido].iloc[0]
                    st.session_state["itens_proposta_rascunho"].append({
                        "Código": str(row_serv["Código"]),
                        "Descrição": str(row_serv["Descrição"]),
                        "Categoria": "Seguro",
                        "Unidade": str(row_serv["Unidade"]),
                        "Tarifa (R$)": float(row_serv["Tarifa (R$)"]),
                        "Observações": str(row_serv["Observações"]) if pd.notna(row_serv["Observações"]) else ""
                    })
                    st.rerun()

    # 3. SERVIÇOS E MOVIMENTAÇÕES
    st.markdown("#### ⚙️ Serviços e Movimentações")
    df_srv = df_servicos[df_servicos["Categoria_Norm"] == "Serviço"]
    df_srv_disp = df_srv[~df_srv["Código"].isin(codigos_ja_adicionados)]

    if df_srv_disp.empty:
        st.info("Nenhum serviço disponível para adicionar.")
    else:
        col_srv1, col_srv2 = st.columns([3, 1])
        with col_srv1:
            opcoes_srv = {f"{r['Código']} - {r['Descrição']}": r['Código'] for _, r in df_srv_disp.iterrows()}
            escolha_srv = st.selectbox("Selecionar Serviço:", options=[""] + list(opcoes_srv.keys()), key="select_srv_prop")
        with col_srv2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Adicionar Serviço", key="btn_add_srv", use_container_width=True):
                if escolha_srv:
                    cod_escolhido = opcoes_srv[escolha_srv]
                    row_serv = df_servicos[df_servicos["Código"] == cod_escolhido].iloc[0]
                    st.session_state["itens_proposta_rascunho"].append({
                        "Código": str(row_serv["Código"]),
                        "Descrição": str(row_serv["Descrição"]),
                        "Categoria": "Serviço",
                        "Unidade": str(row_serv["Unidade"]),
                        "Tarifa (R$)": float(row_serv["Tarifa (R$)"]),
                        "Observações": str(row_serv["Observações"]) if pd.notna(row_serv["Observações"]) else ""
                    })
                    st.rerun()

    # 4. SERVIÇOS CONEXOS
    st.markdown("#### 📦 Serviços Conexos")
    df_con = df_servicos[df_servicos["Categoria_Norm"] == "Serviços Conexos"]
    df_con_disp = df_con[~df_con["Código"].isin(codigos_ja_adicionados)]

    if df_con_disp.empty:
        st.info("Nenhum Serviço Conexo disponível para adicionar.")
    else:
        col_con1, col_con2 = st.columns([3, 1])
        with col_con1:
            opcoes_con = {f"{r['Código']} - {r['Descrição']}": r['Código'] for _, r in df_con_disp.iterrows()}
            escolha_con = st.selectbox("Selecionar Serviços Conexos:", options=[""] + list(opcoes_con.keys()), key="select_con_prop")
        with col_con2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Adicionar Conexos", key="btn_add_con", use_container_width=True):
                if escolha_con:
                    cod_escolhido = opcoes_con[escolha_con]
                    row_serv = df_servicos[df_servicos["Código"] == cod_escolhido].iloc[0]
                    st.session_state["itens_proposta_rascunho"].append({
                        "Código": str(row_serv["Código"]),
                        "Descrição": str(row_serv["Descrição"]),
                        "Categoria": "Serviços Conexos",
                        "Unidade": str(row_serv["Unidade"]),
                        "Tarifa (R$)": float(row_serv["Tarifa (R$)"]),
                        "Observações": str(row_serv["Observações"]) if pd.notna(row_serv["Observações"]) else ""
                    })
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    # ==========================================================================
    # ITENS ADICIONADOS NO RASCUNHO (TABELA EDITÁVEL)
    # ==========================================================================
    st.markdown("### 📋 Itens na Proposta Rascunho")

    if not st.session_state["itens_proposta_rascunho"]:
        st.info("Nenhum item adicionado à proposta rascunho até ao momento.")
    else:
        itens_atualizados = []
        for idx, item in enumerate(st.session_state["itens_proposta_rascunho"]):
            c1, c2, c3, c4, c5, c6 = st.columns([0.5, 1.2, 3, 1.5, 1.5, 3])
            
            with c1:
                if st.button("❌", key=f"del_item_prop_{idx}"):
                    continue  # Remove o item pulando a adição na lista atualizada
            with c2:
                st.text_input("Código", value=str(item["Código"]), disabled=True, key=f"rasc_cod_{idx}")
            with c3:
                st.text_input("Descrição", value=str(item["Descrição"]), disabled=True, key=f"rasc_desc_{idx}")
            with c4:
                nova_tarifa = st.number_input("Tarifa (R$)", value=float(item["Tarifa (R$)"]), format="%.5f", key=f"rasc_tar_{idx}")
            with c5:
                st.text_input("Unidade", value=str(item["Unidade"]), disabled=True, key=f"rasc_un_{idx}")
            with c6:
                nova_obs = st.text_input("Observações", value=str(item["Observações"]), key=f"rasc_obs_{idx}")

            itens_atualizados.append({
                "Código": item["Código"],
                "Descrição": item["Descrição"],
                "Categoria": item["Categoria"],
                "Unidade": item["Unidade"],
                "Tarifa (R$)": nova_tarifa,
                "Observações": nova_obs
            })

        st.session_state["itens_proposta_rascunho"] = itens_atualizados

        st.markdown("<br>", unsafe_allow_html=True)
        col_acao1, col_acao2 = st.columns([2, 1])
        with col_acao2:
            if st.button("🚀 Finalizar Lançamento e Ir para Proposta Cliente", type="primary", use_container_width=True):
                if not cliente_input.strip():
                    st.error("⚠️ Preencha o nome do cliente antes de finalizar.")
                else:
                    linhas_para_salvar = []
                    data_hoje = datetime.now().isoformat()
                    for item in st.session_state["itens_proposta_rascunho"]:
                        linhas_para_salvar.append({
                            "Proposta": num_proposta_atual,
                            "Data": data_hoje,
                            "Cliente": cliente_input.strip(),
                            "CNPJ": cnpj_input.strip(),
                            "Código": item["Código"],
                            "Descrição": item["Descrição"],
                            "Categoria": item["Categoria"],
                            "Unidade": item["Unidade"],
                            "Tarifa (R$)": item["Tarifa (R$)"],
                            "Observações": item["Observações"]
                        })
                    
                    from __main__ import salvar_propostas_no_supabase
                    if salvar_propostas_no_supabase(linhas_para_salvar):
                        st.success("Proposta gravada com sucesso no Supabase!")
                        st.session_state["aba_ativa"] = "cliente"
                        st.rerun()
