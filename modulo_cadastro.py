import streamlit as st
import pandas as pd

def renderizar_aba_cadastro(carregar_dados_fn, salvar_dados_completos_fn, normalizar_codigo_fn, formatar_tarifa_fn):
    st.markdown("## 📋 Cadastro e Gestão de Serviços")
    st.caption("Cadastre, edite ou inative os serviços e tarifas da tabela comercial.")
    st.markdown("<br>", unsafe_allow_html=True)

    # Carrega dados completos (incluindo inativos para gestão)
    try:
        df_completo = carregar_dados_fn(apenas_ativos=False)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        df_completo = pd.DataFrame(columns=["Código", "Descrição", "Tarifa (R$)", "Unidade", "Categoria", "Observações", "Status"])

    colunas_req = ["Código", "Descrição", "Tarifa (R$)", "Unidade", "Categoria", "Observações", "Status"]
    for col in colunas_req:
        if col not in df_completo.columns:
            df_completo[col] = "Ativo" if col == "Status" else ""

    tab_cad, tab_lista = st.tabs(["➕ Novo Serviço", "✏️ Gestão e Edição de Serviços"])

    with tab_cad:
        st.subheader("Adicionar Novo Serviço")
        with st.form("form_novo_servico", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código do Serviço *")
                descricao = st.text_input("Descrição do Serviço *")
                tarifa = st.number_input("Tarifa (R$) *", min_value=0.0, format="%.5f", value=0.0)
            with col2:
                unidade = st.selectbox("Unidade *", st.session_state.get("lista_unidades", ["", "Por caixa", "por unidade", "por pallet", "por hora/homem", "por mês"]))
                categoria = st.selectbox("Categoria *", ["Armazenagem", "Seguro", "Serviço", "Serviços Conexos"])
                observacoes = st.text_area("Observações")

            submitted = st.form_submit_button("💾 Salvar Serviço")
            if submitted:
                cod_norm = normalizar_codigo_fn(codigo)
                if not cod_norm or not descricao.strip():
                    st.error("Preencha os campos obrigatórios (* Código e Descrição).")
                else:
                    if not df_completo.empty and cod_norm in df_completo["Código"].astype(str).values:
                        st.error(f"Erro: O código '{cod_norm}' já está cadastrado.")
                    else:
                        novo_reg = pd.DataFrame([{
                            "Código": cod_norm,
                            "Descrição": descricao.strip(),
                            "Tarifa (R$)": float(tarifa),
                            "Unidade": unidade,
                            "Categoria": categoria,
                            "Observações": observacoes.strip(),
                            "Status": "Ativo"
                        }])
                        df_completo = pd.concat([df_completo, novo_reg], ignore_index=True)
                        if salvar_dados_completos_fn(df_completo):
                            st.success("Serviço cadastrado com sucesso!")
                            st.rerun()

    with tab_lista:
        st.subheader("Lista e Edição de Serviços Existentes")
        if df_completo.empty:
            st.info("Nenhum serviço registado.")
        else:
            df_editado = st.data_editor(
                df_completo,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_servicos_cad"
            )

            if st.button("💾 Salvar Alterações na Tabela", type="primary"):
                try:
                    codigos_lista = [normalizar_codigo_fn(c) for c in df_editado["Código"].astype(str).tolist() if str(c).strip() != ""]
                    if len(codigos_lista) != len(set(codigos_lista)):
                        st.error("Erro: Existem códigos duplicados na tabela. Corrija antes de salvar.")
                    else:
                        if salvar_dados_completos_fn(df_editado):
                            st.success("Alterações guardadas com sucesso!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar alterações: {e}")
