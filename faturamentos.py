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
