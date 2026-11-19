import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pandas as pd
import calendar
from supabase import create_client


def obter_feriados_brasil(ano):
    return [
        datetime(ano, 1, 1).date(),
        datetime(ano, 4, 21).date(),
        datetime(ano, 5, 1).date(),
        datetime(ano, 9, 7).date(),
        datetime(ano, 10, 12).date(),
        datetime(ano, 11, 2).date(),
        datetime(ano, 11, 15).date(),
        datetime(ano, 11, 20).date(),
        datetime(ano, 12, 25).date(),
    ]


def eh_dia_util(data):
    if data.weekday() >= 5:
        return False
    if data in obter_feriados_brasil(data.year):
        return False
    return True


def ajustar_dia_util(data_obj, direcao="retroceder"):
    while not eh_dia_util(data_obj):
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


def calcular_dias_uteis_restantes(data_alvo, data_atual):
    if data_alvo <= data_atual:
        return (data_alvo - data_atual).days
    dias_uteis = 0
    cur_date = data_atual + timedelta(days=1)
    while cur_date <= data_alvo:
        if eh_dia_util(cur_date):
            dias_uteis += 1
        cur_date += timedelta(days=1)
    return dias_uteis


def normalizar_quebras_email(texto):
    texto_limpo = texto.replace("\r\n", "\n").replace("\r", "\n")
    return texto_limpo.replace("\n", "\r\n")


def enviar_email(provedor, remetente, senha, destinos_str, assunto, corpo):
    corpo_smtp = normalizar_quebras_email(corpo)
    try:
        if provedor == "Gmail":
            smtp_server = "smtp.gmail.com"
            port = 587
        else:
            smtp_server = "smtp.office365.com"
            port = 587

        destinos = [d.strip() for d in destinos_str.replace(";", ",").split(",") if d.strip()]
        if not destinos:
            return False, "Nenhum destino válido."

        server = smtplib.SMTP(smtp_server, port, timeout=10)
        server.starttls()
        server.login(remetente, senha)

        sucessos = 0
        erros = []
        for destino in destinos:
            try:
                msg = MIMEMultipart()
                msg['From'] = remetente
                msg['To'] = destino
                msg['Subject'] = assunto
                msg.attach(MIMEText(corpo_smtp, 'plain', 'utf-8'))
                server.sendmail(remetente, destino, msg.as_string())
                sucessos += 1
            except Exception as ex:
                erros.append(f"{destino}: {ex}")

        server.quit()
        if sucessos > 0:
            return True, f"Enviado para {sucessos} destinatário(s)"
        return False, str(erros)
    except Exception as e:
        return False, str(e)


def registrar_log(supabase_client, tipo, destinatario, assunto, status, detalhes):
    try:
        log_data = {
            "tipo": tipo,
            "destinatario": destinatario,
            "assunto": assunto,
            "status": status,
            "detalhes": detalhes,
            "data_envio": datetime.now().isoformat()
        }
        supabase_client.table("logs_envios").insert(log_data).execute()
    except Exception:
        pass


def executar_cron_geral():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        print("Erro: Credenciais do Supabase não encontradas.")
        return

    supabase = create_client(url, key)
    hoje = datetime.now().date()

    # ==========================================
    # 1. PROCESSAMENTO DE CONTRATOS
    # ==========================================
    try:
        res_cfg = supabase.table("config_email").select("*").eq("id", 1).execute()
        if res_cfg.data:
            cfg = res_cfg.data[0]
            prov_c = cfg.get("provedor", "Outlook / Office365")
            rem_c = cfg.get("email_remetente")
            sen_c = cfg.get("senha_remetente")
            comercial = cfg.get("email_comercial_globex")

            if rem_c and sen_c:
                res_cont = supabase.table("contratos").select("*").execute()
                for item in (res_cont.data or []):
                    cid = item['id']
                    cliente = item['cliente']
                    num_contrato = item['num_contrato']
                    data_fim_str = item['data_fim']
                    email_cliente = item['email_cliente']
                    a45 = item.get('alerta_45_enviado', 0)
                    a30 = item.get('alerta_30_enviado', 0)
                    tipo_doc = item.get('tipo', 'Contrato')
                    objeto_doc = item.get('objeto', 'Armazenagem')

                    data_fim = datetime.strptime(str(data_fim_str)[:10], "%Y-%m-%d").date()
                    dias_restantes = (data_fim - hoje).days

                    if 30 < dias_restantes <= 45 and a45 == 0 and comercial:
                        assunto = f"[ALERTA RENOVAÇÃO] {tipo_doc} próxima de vencer - {cliente}"
                        corpo = (
                            "Atenção Comercial Globex,\n\n"
                            "Existe um documento próximo ao período de renovação.\n\n"
                            f"- Cliente: {cliente}\n"
                            f"- Tipo: {tipo_doc}\n"
                            f"- Objeto: {objeto_doc}\n"
                            f"- Nº Documento: {num_contrato}\n"
                            f"- Data de Vencimento: {data_fim.strftime('%d/%m/%Y')}\n"
                            f"- Dias restantes: {dias_restantes}\n\n"
                            "Atenciosamente,\n"
                            "Globex Multimodal"
                        )
                        suc, err = enviar_email(prov_c, rem_c, sen_c, comercial, assunto, corpo)
                        if suc:
                            supabase.table("contratos").update({"alerta_45_enviado": 1, "status": "Informado ao comercial por email"}).eq("id", cid).execute()
                            registrar_log(supabase, f"Alerta 45 Dias (Comercial) - {tipo_doc}", comercial, assunto, "Sucesso", f"{tipo_doc} {num_contrato}")

                    elif dias_restantes <= 30 and a30 == 0 and email_cliente:
                        assunto = f"Globex Multimodal - Renovação de {tipo_doc} Nº {num_contrato} ({objeto_doc})"
                        corpo = (
                            f"Prezado(a) cliente {cliente},\n\n"
                            "Existe um documento próximo ao período de renovação.\n\n"
                            f"- Cliente: {cliente}\n"
                            f"- Tipo: {tipo_doc}\n"
                            f"- Objeto: {objeto_doc}\n"
                            f"- Nº Documento: {num_contrato}\n"
                            f"- Data de Vencimento: {data_fim.strftime('%d/%m/%Y')}\n"
                            f"- Dias restantes: {dias_restantes}\n\n"
                            "Aguarde o contato de nossa equipe.\n\n"
                            "Atenciosamente,\n"
                            "Globex Multimodal"
                        )
                        suc, err = enviar_email(prov_c, rem_c, sen_c, email_cliente, assunto, corpo)
                        if suc:
                            supabase.table("contratos").update({"alerta_30_enviado": 1, "status": "Informado ao cliente por email"}).eq("id", cid).execute()
                            registrar_log(supabase, f"Alerta 30 Dias (Cliente) - {tipo_doc}", email_cliente, assunto, "Sucesso", f"{tipo_doc} {num_contrato}")
    except Exception as e:
        print(f"Erro no cron de contratos: {e}")

    # ==========================================
    # 2. PROCESSAMENTO DE FATURAMENTOS
    # ==========================================
    try:
        res_cfg_fat = supabase.table("config_email_faturamento").select("*").eq("id", 1).execute()
        if res_cfg_fat.data:
            cfg_fat = res_cfg_fat.data[0]
            prov_f = cfg_fat.get("provedor", "Outlook / Office365")
            rem_f = cfg_fat.get("email_remetente")
            sen_f = cfg_fat.get("senha_remetente")
            destinos_f = cfg_fat.get("emails_destino", "")

            if rem_f and sen_f and destinos_f:
                res_fat = supabase.table("faturamentos").select("*").eq("status", "Ativo").execute()
                res_cont = supabase.table("contratos").select("num_contrato, data_fim").execute()
                map_vencimentos = {str(c['num_contrato']): str(c['data_fim']) for c in (res_cont.data or []) if c.get('num_contrato') and c.get('data_fim')}

                for item in (res_fat.data or []):
                    rid = item['id']
                    cliente = item['cliente']
                    num_prop = str(item['id_contrato'])
                    condicao = item['condicao']
                    inicio_str = item['inicio_periodo']
                    alerta_enviado = item.get('alerta_enviado', 0) or 0
                    dia_fixo = int(item['dia_fixo']) if (item.get('dia_fixo') is not None) else 10
                    pular_mes = bool(item.get('pular_mes_atual', False))

                    inicio_dt = datetime.strptime(inicio_str, "%Y-%m-%d").date()
                    data_fatura = calcular_previsao_faturamento(condicao, inicio_dt, dia_fixo, pular_mes)

                    if num_prop in map_vencimentos:
                        try:
                            venc_dt = datetime.strptime(map_vencimentos[num_prop], "%Y-%m-%d").date()
                            if data_fatura >= venc_dt:
                                data_fatura = venc_dt
                        except Exception:
                            pass

                    if data_fatura < hoje:
                        novo_mes = inicio_dt.month % 12 + 1
                        novo_ano = inicio_dt.year + (1 if inicio_dt.month == 12 else 0)
                        novo_dia = min(inicio_dt.day, calendar.monthrange(novo_ano, novo_mes)[1])
                        novo_inicio_str = datetime(novo_ano, novo_mes, novo_dia).strftime("%Y-%m-%d")
                        supabase.table("faturamentos").update({"inicio_periodo": novo_inicio_str, "alerta_enviado": 0}).eq("id", rid).execute()
                        continue

                    dias_uteis_restantes = calcular_dias_uteis_restantes(data_fatura, hoje)

                    # 2 dias úteis antes
                    if dias_uteis_restantes == 2 and alerta_enviado < 1:
                        assunto = f"[ALERTA OPERACIONAL] Preparação de Faturamento - Proposta Nº {num_prop} ({cliente})"
                        corpo = (
                            "Atenção Equipe Operacional,\n\n"
                            "Este é um aviso automático de preparação de faturamento.\n\n"
                            f"- Cliente: {cliente}\n"
                            f"- Nº Proposta / Contrato: {num_prop}\n"
                            f"- Condição de Faturamento: {condicao}\n"
                            f"- Data Prevista: {data_fatura.strftime('%d/%m/%Y')}\n"
                            "- Status: Faltam 2 dias úteis para a data limite de preparação dos dados\n\n"
                            "Por favor, certifiquem-se de que as medições e informações operacionais estão em andamento.\n\n"
                            "Atenciosamente,\n"
                            "Globex Multimodal"
                        )
                        suc, err = enviar_email(prov_f, rem_f, sen_f, destinos_f, assunto, corpo)
                        if suc:
                            supabase.table("faturamentos").update({"alerta_enviado": 1}).eq("id", rid).execute()
                            registrar_log(supabase, "Cron Faturamento - 2 dias úteis", destinos_f, assunto, "Sucesso", f"Proposta {num_prop}")

                    # 1 dia útil antes
                    elif dias_uteis_restantes == 1 and alerta_enviado < 2:
                        assunto = f"[ALERTA OPERACIONAL] Véspera de Faturamento - Proposta Nº {num_prop} ({cliente})"
                        corpo = (
                            "Atenção Equipe Operacional,\n\n"
                            "Este é um aviso de véspera de faturamento.\n\n"
                            f"- Cliente: {cliente}\n"
                            f"- Nº Proposta / Contrato: {num_prop}\n"
                            f"- Condição de Faturamento: {condicao}\n"
                            f"- Data Prevista: AMANHÃ ({data_fatura.strftime('%d/%m/%Y')})\n"
                            "- Status: 1 dia útil restante para emissão/envio\n\n"
                            "Certifiquem-se de que todos os dados estão prontos para o faturamento de amanhã.\n\n"
                            "Atenciosamente,\n"
                            "Globex Multimodal"
                        )
                        suc, err = enviar_email(prov_f, rem_f, sen_f, destinos_f, assunto, corpo)
                        if suc:
                            supabase.table("faturamentos").update({"alerta_enviado": 2}).eq("id", rid).execute()
                            registrar_log(supabase, "Cron Faturamento - 1 dia útil", destinos_f, assunto, "Sucesso", f"Proposta {num_prop}")

                    # No próprio dia
                    elif dias_uteis_restantes <= 0 and alerta_enviado < 3:
                        assunto = f"[URGENTE - HOJE] Prazo de Faturamento - Proposta Nº {num_prop} ({cliente})"
                        corpo = (
                            "Atenção Equipe Operacional,\n\n"
                            "O prazo limite para a realização do faturamento é HOJE.\n\n"
                            f"- Cliente: {cliente}\n"
                            f"- Nº Proposta / Contrato: {num_prop}\n"
                            f"- Condição de Faturamento: {condicao}\n"
                            f"- Data Prevista: HOJE ({data_fatura.strftime('%d/%m/%Y')})\n"
                            "- Status: Faturamento programado para execução hoje\n\n"
                            "Por favor, confirmem e finalizem a emissão com urgência.\n\n"
                            "Atenciosamente,\n"
                            "Globex Multimodal"
                        )
                        suc, err = enviar_email(prov_f, rem_f, sen_f, destinos_f, assunto, corpo)
                        if suc:
                            supabase.table("faturamentos").update({"alerta_enviado": 3}).eq("id", rid).execute()
                            registrar_log(supabase, "Cron Faturamento - Hoje", destinos_f, assunto, "Sucesso", f"Proposta {num_prop}")
    except Exception as e:
        print(f"Erro no cron de faturamentos: {e}")


if __name__ == "__main__":
    executar_cron_geral()
