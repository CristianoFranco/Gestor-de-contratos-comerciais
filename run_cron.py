import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client

def obter_feriados_brasil(ano):
    """Retorna uma lista de datas correspondentes aos feriados nacionais fixos e principais móveis do Brasil para o ano."""
    feriados = [
        datetime(ano, 1, 1).date(),   # Confraternização Universal
        datetime(ano, 4, 21).date(),  # Tiradentes
        datetime(ano, 5, 1).date(),   # Dia do Trabalhador
        datetime(ano, 9, 7).date(),   # Independência do Brasil
        datetime(ano, 10, 12).date(), # Nossa Senhora Aparecida
        datetime(ano, 11, 2).date(),  # Finados
        datetime(ano, 11, 15).date(), # Proclamação da República
        datetime(ano, 11, 20).date(), # Consciência Negra
        datetime(ano, 12, 25).date(), # Natal
    ]
    
    # Cálculo aproximado da Páscoa / Carnaval / Corpus Christi (ou feriados móveis relevantes se necessário)
    # Para maior precisão, podemos adicionar a verificação de dias festivos móveis ou focar nos nacionais fixos e facultativos.
    return feriados

def eh_dia_util(data):
    """Verifica se a data é um dia útil (não é sábado, domingo ou feriado nacional)."""
    if data.weekday() >= 5:  # Sábado (5) ou Domingo (6)
        return False
    
    feriados_ano = obter_feriados_brasil(data.year)
    if data in feriados_ano:
        return False
        
    return True

def calcular_dias_uteis_ate(data_alvo, data_atual):
    """Calcula a quantidade de dias úteis entre a data atual e a data alvo (excluindo fins de semana e feriados)."""
    if data_atual >= data_alvo:
        return 0
    
    dias_uteis = 0
    data_iter = data_atual + timedelta(days=1)
    while data_iter <= data_alvo:
        if eh_dia_util(data_iter):
            dias_uteis += 1
        data_iter += timedelta(days=1)
    return dias_uteis

def enviar_email(provedor, remetente, senha, destino, assunto, corpo):
    try:
        if provedor == "Gmail":
            smtp_server = "smtp.gmail.com"
            port = 587
        else:
            smtp_server = "smtp.office365.com"
            port = 587

        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destino
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'plain'))

        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        return True, "Enviado com sucesso"
    except Exception as e:
        return False, str(e)

def executar_cron_faturamentos():
    try:
        url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    except Exception:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        print("Erro: Credenciais do Supabase não encontradas.")
        return

    supabase = create_client(url, key)

    # Carregar configurações de e-mail
    try:
        res_cfg = supabase.table("config_email").select("*").eq("id", 1).execute()
        if not res_cfg.data:
            print("Configurações de e-mail não encontradas.")
            return
        cfg = res_cfg.data[0]
        provedor = cfg.get("provedor", "Outlook / Office365")
        remetente = cfg.get("email_remetente")
        senha = cfg.get("senha_remetente")
        comercial = cfg.get("email_comercial_globex")
    except Exception as e:
        print(f"Erro ao carregar configurações de e-mail: {e}")
        return

    if not remetente or not senha:
        print("Credenciais de remetente vazias.")
        return

    # Buscar faturamentos ativos
    try:
        res_fat = supabase.table("faturamentos").select("*").eq("status", "Ativo").execute()
        faturamentos = res_fat.data
    except Exception as e:
        print(f"Erro ao buscar faturamentos: {e}")
        return

    hoje = datetime.now().date()

    for fat in faturamentos:
        fid = fat['id']
        cliente = fat['cliente']
        id_contrato = fat['id_contrato']
        condicao = fat['condicao']
        data_inicio_str = fat['inicio_periodo']
        email_cliente = fat.get('email_cliente')
        alerta_atual = fat.get('alerta_envidado', 0)
        
        if not email_cliente or email_cliente.upper() == "NULL" or email_cliente.upper() == "EMPTY":
            continue

        data_inicio = datetime.strptime(str(data_inicio_str)[:10], "%Y-%m-%d").date()

        # Calcula a data prevista de faturamento com base na condição
        if condicao == "Data Fixa":
            dia_f = int(fat.get('dia_fixo', 1))
            try:
                data_prevista = datetime(hoje.year, hoje.month, dia_f).date()
            except ValueError:
                data_prevista = data_inicio
        elif condicao == "30 dias após inicio":
            data_prevista = data_inicio + timedelta(days=30)
        else: # Fim do mês
            if hoje.month == 12:
                proximo_mes = datetime(hoje.year + 1, 1, 1)
            else:
                proximo_mes = datetime(hoje.year, hoje.month + 1, 1)
            data_prevista = (proximo_mes - timedelta(days=1)).date()

        # Se a data prevista já passou ou é hoje
        if data_prevista < hoje:
            continue

        # Calcula dias úteis restantes até o vencimento/faturamento (ignorando fins de semana e feriados)
        dias_uteis = calcular_dias_uteis_ate(data_prevista, hoje)
        
        disparar = False
        tipo_alerta = ""

        if dias_uteis == 2 and alerta_atual < 1:
            disparar = True
            novo_alerta = 1
            tipo_alerta = "2 dias úteis para o faturamento"
        elif dias_uteis == 1 and alerta_atual < 2:
            disparar = True
            novo_alerta = 2
            tipo_alerta = "1 dia útil para o faturamento"
        elif dias_uteis == 0 and alerta_atual < 3:
            disparar = True
            novo_alerta = 3
            tipo_alerta = "Faturamento programado para hoje"

        if disparar:
            assunto = f"Globex Multimodal - Aviso de Faturamento ({cliente})"
            corpo = f"Prezado(a),\n\nEste é um aviso automático referente ao faturamento do contrato/proposta {id_contrato} para o cliente {cliente}.\nStatus: {tipo_alerta}.\nData prevista: {data_prevista.strftime('%d/%m/%Y')}.\n\nAtenciosamente,\nGlobex Multimodal"

            sucesso, msg_err = enviar_email(provedor, remetente, senha, email_cliente, assunto, corpo)
            
            # Se houver e-mail comercial configurado, envia cópia também
            if comercial and comercial.strip():
                enviar_email(provedor, remetente, senha, comercial, f"[COMERCIAL] {assunto}", corpo)

            if sucesso:
                supabase.table("faturamentos").update({"alerta_envidado": novo_alerta}).eq("id", fid).execute()
                print(f"Alerta ({tipo_alerta}) enviado para {email_cliente} referente ao faturamento ID {fid}.")
            else:
                print(f"Erro ao enviar e-mail para ID {fid}: {msg_err}")

if __name__ == "__main__":
    executar_cron_faturamentos()
