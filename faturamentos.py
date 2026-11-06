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

    # Conexão Supabase com tratamento de erro
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase = create_client(url, key)
    except Exception as e:
        st.error(f"Erro crítico ao conectar ao Supabase: {e}")
        return

    # Carregar configurações de e-mail específicas do Faturamento
    @st.cache_data(ttl=60)
    def carregar_config_email_faturamento():
        try:
            res = supabase.table("config_email_faturamento").select("*").eq("id", 1).execute()
            if res.data:
                return res.data[0]
        except Exception:
            pass
        return {}

    config_db = carregar_config_email_faturamento()

    # Inicializar session_state para as configurações de e-mail
    if "fat_provedor" not in st.session_state:
        st.session_state["fat_provedor"] = config_db.get("provedor", "Outlook / Office365")
    if "fat_email_remetente" not in st.session_state:
        st.session_state["fat_email_remetente"] = config_db.get("email_remetente", "")
    if "fat_senha_remetente" not in st.session_state:
        st.session_state["fat_senha_remetente"] = config_db.get("senha_remetente", "")
    if "fat_emails_destino" not in st.session_state:
        st.session_state["fat_emails_destino"] = config_db.get("emails_destino", "")

    def enviar_email_para_todos(provedor, email_remetente, senha, lista_destinos, assunto, mensagem, cliente, proposta):
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
            d_fixo = min(int(dia_fixo), calendar.monthrange(base_
