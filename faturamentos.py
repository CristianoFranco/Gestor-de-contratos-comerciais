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
    while data_obj.weekday() >= 5:
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
        if cur_date.weekday() < 5:
            dias_uteis += 1
        cur_date += timedelta(days=1)
    return dias_uteis

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

        res_cont = supabase.table("contratos").select("num_contrato, data_fim").execute()
        map_vencimentos = {}
        if res_cont and res_cont.data:
            for c in res_cont.data:
                if c.get('num_contrato') and c.get('data_fim'):
                    map_vencimentos[str(c['num_contrato'])] = str(c['data_fim'])

        hoje = datetime.now().date()
        disparos = 0

        for item in registros:
            rid = item['id']
            cliente = item['cliente']
            num_prop = str(item['id_contrato'])
            condicao = item['condicao']
            inicio_str = item['inicio_periodo']
            alerta_enviado = item.get('alerta_enviado', 0) or 0
            dia_fixo = int(item['dia_fixo']) if (item.get('dia_fixo') is not None) else 10
            pular_mes = bool(item.get('pular_mes_atual', False)) if item.get('pular_mes_atual') is not None else False

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
                
                supabase.table("faturamentos").update({
                    "inicio_periodo": novo_inicio_str,
                    "alerta_enviado": 0
                }).eq("id", rid).execute()
                continue

            dias_uteis_restantes = calcular_dias_uteis_restantes(data_fatura, hoje)

            if dias_uteis_restantes == 2 and alerta_enviado < 1:
                assunto = f"[ALERTA OPERACIONAL] Preparação de Faturamento - Proposta Nº {num_prop} ({cliente})"
                corpo = f"Atenção Equipa,\n\nO faturamento para o cliente {cliente} (Proposta Nº {num_prop}, Condição: {condicao}) tem data prevista para {data_fatura.strftime('%d/%m/%Y')}.\nFaltam 2 dias úteis para a data limite de preparação de dados.\n\nAtenciosamente,\nGlobex Multimodal"
                sucesso, err = enviar_email_para_todos(prov, remetente, senha, lista_destinos, assunto, corpo, cliente, num_prop, supabase)
                if sucesso:
                    supabase.table("faturamentos").update({"alerta_enviado": 1}).eq("id", rid).execute()
                    disparos += 1

            elif dias_uteis_restantes == 1 and alerta_enviado < 2:
                assunto = f"[ALERTA OPERACIONAL] Véspera de Faturamento - Proposta Nº {num_prop} ({cliente})"
                corpo = f"Atenção Equipa,\n\nO faturamento para o cliente {cliente} (Proposta Nº {num_prop}, Condição: {condicao}) tem data prevista para AMANHÃ ({data_fatura.strftime('%d/%m/%Y')}).\nCertifiquem-se de que os dados estão prontos.\n\nAtenciosamente,\nGlobex Multimodal"
                sucesso, err = enviar_email_para_todos(prov, remetente, senha, lista_destinos, assunto, corpo, cliente, num_prop, supabase)
                if sucesso:
                    supabase.table("faturamentos").update({"alerta_enviado": 2}).eq("id", rid).execute()
                    disparos += 1

            elif dias_uteis_restantes <= 0 and alerta_enviado < 3:
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
        st.session_state["fat_provedor"] = config_db.get("provedor", "Outlook
