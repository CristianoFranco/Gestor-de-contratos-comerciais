with col_acao2:
                    if st.button("🔒 Encerrar Contrato (Remover do Painel)"):
                        # Verificação rigorosa de segurança para faturamentos ativos usando o ID do contrato
                        faturamento_ativo_encontrado = False
                        try:
                            # Consulta os faturamentos associados a este ID de contrato específico
                            res_fat = supabase.table("faturamentos").select("*").eq("id_contrato", contrato_id).execute()
                            if res_fat.data:
                                df_fat = pd.DataFrame(res_fat.data)
                                if 'status' in df_fat.columns:
                                    match_fat = df_fat[df_fat['status'].astype(str).str.strip().str.lower() == 'ativo']
                                    if not match_fat.empty:
                                        faturamento_ativo_encontrado = True
                        except Exception as e:
                            # Fallback caso a coluna mude ou ocorra outro detalhe
                            pass

                        if faturamento_ativo_encontrado:
                            st.error("🚫 **Operação Bloqueada:** Não é possível encerrar este contrato pois existe um faturamento ativo vinculado a ele. Por favor, vá ao gestor de faturamentos e encerre o faturamento primeiro.")
                        else:
                            try:
                                supabase.table("contratos").delete().eq("id", contrato_id).execute()
                                st.success("Contrato encerrado e removido do painel com sucesso!")
                                st.rerun()
                            except Exception as e:
                                # Mensagem de erro amigável e limpa para o utilizador
                                st.error("⚠️ Não foi possível excluir o contrato devido a uma restrição de integridade no banco de dados. Verifique se existem registos dependentes.")
