with col_acao2:
                    if st.button("🔒 Encerrar Contrato (Remover do Painel)"):
                        # Captura tanto o ID interno quanto o número do contrato exato
                        id_contrato_alvo = str(contrato_id).strip()
                        num_contrato_alvo = str(contrato_atual['num_contrato']).strip()
                        
                        faturamento_ativo_encontrado = False
                        try:
                            res_fat = supabase.table("faturamentos").select("*").execute()
                            if res_fat.data:
                                df_fat = pd.DataFrame(res_fat.data)
                                if 'id_contrato' in df_fat.columns and 'status' in df_fat.columns:
                                    # Verifica se existe algum faturamento ativo cujo id_contrato corresponda ao ID ou ao número do contrato
                                    match_fat = df_fat[
                                        (
                                            (df_fat['id_contrato'].astype(str).str.strip() == id_contrato_alvo) | 
                                            (df_fat['id_contrato'].astype(str).str.strip() == num_contrato_alvo)
                                        ) & 
                                        (df_fat['status'].astype(str).str.strip().str.lower() == 'ativo')
                                    ]
                                    if not match_fat.empty:
                                        faturamento_ativo_encontrado = True
                        except Exception:
                            pass

                        if faturamento_ativo_encontrado:
                            st.error("🚫 **Operação Bloqueada:** Não foi possível excluir o contrato devido a haver faturamentos programados ou ativos vinculados. Por favor, encerre os faturamentos associados primeiro.")
                        else:
                            try:
                                supabase.table("contratos").delete().eq("id", contrato_id).execute()
                                st.success("Contrato encerrado e removido do painel com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error("🚫 **Operação Bloqueada:** Não foi possível excluir o contrato devido a haver faturamentos programados na base de dados.")
