with tab_cad:
            st.subheader("Novo Contrato")
            
            with st.form("form_novo_contrato", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    cliente = st.text_input("Nome do Cliente *")
                    num_contrato = st.text_input("Número do Contrato *")
                    
                    # Campo de data com conversão amigável e formato padrão BR visível
                    data_inicio_input = st.date_input("Data de Início do Contrato", datetime.now())
                    data_inicio_br = data_inicio_input.strftime('%d/%m/%Y')
                    st.markdown(f"<span style='color: #0c3547; font-size: 13px; font-weight: bold;'>📅 Data selecionada: {data_inicio_br}</span>", unsafe_allow_html=True)
                
                with col2:
                    email_cliente = st.text_input("E-mail do Cliente *")
                    telefone_cliente = st.text_input("Telefone do Cliente *")
                    vigencia_meses = st.number_input("Vigência / Período do Reajuste (em Meses) *", min_value=1, value=12, step=1)

                total_meses = int(vigencia_meses)
                
                # Cálculo exato por meses civis (respeitando anos bissextos e fins de mês)
                ano_alvo = data_inicio_input.year + (data_inicio_input.month - 1 + total_meses) // 12
                mes_alvo = (data_inicio_input.month - 1 + total_meses) % 12 + 1
                dia_alvo = data_inicio_input.day
                
                ultimo_dia_mes_alvo = calendar.monthrange(ano_alvo, mes_alvo)[1]
                if dia_alvo > ultimo_dia_mes_alvo:
                    dia_alvo = ultimo_dia_mes_alvo
                    
                data_fim_calculada = datetime(ano_alvo, mes_alvo, dia_alvo).date()
                data_fim_br = data_fim_calculada.strftime('%d/%m/%Y')

                st.info(f"📅 Previsão de Término / Renovação: **{data_fim_br}**")

                submitted = st.form_submit_button("💾 Salvar Contrato")

                if submitted:
                    if not cliente or not num_contrato or not email_cliente:
                        st.error("Por favor, preencha todos os campos obrigatórios (*).")
                    else:
                        try:
                            novo_registro = {
                                "cliente": cliente,
                                "num_contrato": num_contrato,
                                "data_inicio": str(data_inicio_input),
                                "vigencia_meses": vigencia_meses,
                                "data_fim": str(data_fim_calculada),
                                "email_cliente": email_cliente,
                                "telefone_cliente": telefone_cliente,
                                "status": "Ativo",
                                "alerta_45_enviado": 0,
                                "alerta_30_enviado": 0
                            }
                            supabase.table("contratos").insert(novo_registro).execute()
                            st.success("✅ Contrato cadastrado com sucesso! Os campos foram limpos.")
                            st.toast("Contrato salvo com sucesso!", icon="✅")
                        except Exception as e:
                            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                                st.error("Erro: Número de contrato já cadastrado.")
                            else:
                                st.error(f"Erro ao salvar: {e}")
