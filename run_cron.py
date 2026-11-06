import os
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import calendar
from supabase import create_client

def enviar_email_generico(prov, remetente, senha, destino, assunto, corpo):
    try:
        if prov == "Gmail":
            smtp_server = "smtp.gmail.com"
            port = 587
        else:
            smtp_server = "smtp.office365.com"
            port = 587

        server = smtplib.SMTP(smtp_server, port, timeout=10)
        server.starttls()
        server.login(remetente, senha)

        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destino
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'plain'))
        server.send_message(msg)
        server.quit()
        return True
    except Exception as ex:
        print(f"Erro ao enviar e-mail para {destino}: {ex}")
        return False

# ==========================================
# 1. ROTINA DE ALERTAS DE CONTRATOS
# ==========================================
def rodar_automacao_contratos(supabase):
    try:
        res_cfg = supabase.table("config_email").select("*").eq("id", 1).execute()
        if not res_cfg.data:
            print("Configurações de e-mail de contratos não encontradas.")
            return
        cfg = res_cfg.data[0]
        remetente = cfg.get("email_remetente")
        senha = cfg.get("senha_remetente")
        prov = cfg.get("provedor", "Outlook / Office365")
        comercial = cfg.get("email_comercial_globex")

        if not remetente or not senha or not comercial:
            print("Configurações de contratos incompletas.")
            return

        res_cont = supabase.table("contratos").select("*").execute()
        contratos = res_cont.data if res_cont.data else []

        hoje = datetime.now().date()
        disparos = 0

        for item in contratos:
            cid = item['id']
            cliente = item['cliente']
            num_contrato = item['num_contrato']
            data_fim_str = item['data_fim']
            email_cliente = item['email_cliente']
            a45 = item.get('alerta_45_enviado', 0) or 0
            a30 = item.get('alerta_30_enviado', 0) or 0
            
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
            dias_restantes = (data_fim - hoje).days

            # 45 dias -> Comercial Globex
            if 30 < dias_restantes <= 45 and a45 == 0:
                assunto = f"[ALERTA RENOVAÇÃO] Contrato próximo de vencer - {cliente}"
                corpo = f"Atenção Comercial Globex,\n\nExiste um contrato próximo ao período de renovação.\n\nCliente: {cliente}\nNº Contrato: {num_contrato}\nData de Vencimento: {data_fim.strftime('%d/%m/%Y')}\nDias restantes: {dias_restantes}"
                if enviar_email_generico(prov, remetente, senha, comercial, assunto, corpo):
                    supabase.table("contratos").update({"alerta_45_enviado": 1, "status": "Informado ao comercial por email"}).eq("id", cid).execute()
                    disparos += 1

            # 30 dias -> Cliente
            elif dias_restantes <= 30 and a30 == 0:
                assunto = f"Globex Multimodal - Renovação de Contrato Nº {num_contrato}"
                corpo = f"Prezado(a) cliente {cliente},\n\nSeu contrato está chegando próximo à renovação. Aguarde contato da Globex.\n\nAtenciosamente,\nGlobex Multimodal"
                if enviar_email_generico(prov, remetente, senha, email_cliente, assunto, corpo):
                    supabase.table("contratos").update({"alerta_30_enviado": 1, "status": "Informado ao cliente por email"}).eq("id", cid).execute()
                    disparos += 1
                    
        print(f"Automação de Contratos concluída. Alertas disparados: {disparos}")
    except Exception as e:
        print(f"Erro na automação de contratos: {e}")

# ==========================================
# 2. ROTINA DE ALERTAS DE FATURAMENTOS
# ==========================================
def calcular_previsao_fat(condicao, inicio_dt, dia_fixo=10, pular_mes_atual=False):
    if isinstance(inicio_dt, str):
        inicio_dt = datetime.strptime(inicio_dt, "%Y-%m-%d").date()

    base_dt = inicio_dt
    if pular_mes_atual:
        mes_seguinte = inicio_dt.month % 12 + 1
        ano_seguinte = inicio_dt.year + (1 if inicio_dt.month == 12 else 0)
        base_dt = datetime(ano_seguinte, mes_seguinte, min(inicio_dt.day, calendar.monthrange(ano_seguinte, mes_seguinte)[1])).date()

    def ajustar_dia_util(d_obj, direcao="retroceder"):
        while d_obj.weekday() >= 5:
            d_obj = d_obj - timedelta(days=1) if direcao == "retroceder" else d_obj + timedelta(days=1)
        return d_obj

    if condicao == "30 dias após inicio":
        dt_fat = ajustar_dia_util(base_dt + timedelta(days=30), "avancar")
    elif condicao == "Data Fixa":
        d_f = min(int(dia_fixo), calendar.monthrange(base_dt.year, base_dt.month)[1])
        dt_fat = datetime(base_dt.year, base_dt.month, d_f).date()
        if dt_fat < base_dt:
            m_prox = base_dt.month % 12 + 1
            a_prox = base_dt.year + (1 if base_dt.month == 12 else 0)
            d_f_prox = min(int(dia_fixo), calendar.monthrange(a_prox, m_prox)[1])
            dt_fat = datetime(a_prox, m_prox, d_f_prox).date()
        dt_fat = ajustar_dia_util(dt_fat, "retroceder")
    elif condicao == "1º dia útil do mês":
        prim = datetime(base_dt.year, base_dt.month, 1).date()
        dt_fat = ajustar_dia_util(prim, "avancar")
        if not pular_mes_atual and base_dt > dt_fat:
            m_prox = base_dt.month % 12 + 1
            a_prox = base_dt.year + (1 if base_dt.month == 12 else 0)
            dt_fat = ajustar_dia_util(datetime(a_prox, m_prox, 1).date(), "avancar")
    elif condicao == "Penúltimo dia do mês":
        ult_n = calendar.monthrange(base_dt.year, base_dt.month)[1]
        dt_fat = ajustar_dia_util(datetime(base_dt.year, base_dt.month, ult_n - 1).date(), "retroceder")
        if not pular_mes_atual and base_dt > dt_fat:
            m_prox = base_dt.month % 12 + 1
            a_prox = base_dt.year + (1 if base_dt.month == 12 else 0)
            ult_n_prox = calendar.monthrange(a_prox, m_prox)[1]
            dt_fat = ajustar_dia_util(datetime(a_prox, m_prox, ult_n_prox - 1).date(), "retroceder")
    elif condicao == "Fim do mês":
        ult_n = calendar.monthrange(base_dt.year, base_dt.month)[1]
        dt_fat = ajustar_dia_util(datetime(base_dt.year, base_dt.month, ult_n).date(), "retroceder")
        if not pular_mes_atual and base_dt > dt_fat:
            m_prox = base_dt.month % 12 + 1
            a_prox = base_dt.year + (1 if base_dt.month == 12 else 0)
            ult_n_prox = calendar.monthrange(a_prox, m_prox)[1]
            dt_fat = ajustar_dia_util(datetime(a_prox, m_prox, ult_n_prox).date(), "retroceder")
    else:
        dt_fat = base_dt
    return dt_fat

def rodar_automacao_faturamentos(supabase):
    try:
        res_cfg = supabase.table("config_email_faturamento").select("*").eq("id", 1).execute()
        if not res_cfg.data:
            print("Configurações de e-mail de faturamento não encontradas.")
            return
        cfg_fat = res_cfg.data[0]
        remetente = cfg_fat.get("email_remetente")
        senha = cfg_fat.get("senha_remetente")
        prov = cfg_fat.get("provedor", "Outlook / Office365")
        destinos_str = cfg_fat.get("emails_destino", "")

        if not remetente or not senha or not destinos_str:
            return

        lista_destinos = [e.strip() for e in destinos_str.replace(";", ",").split(",") if e.strip()]
        if not lista_destinos:
            return

        res_fat = supabase.table("faturamentos").select("*").eq("status", "Ativo").execute()
        registros = res_fat.data if res_fat.data else []

        res_cont = supabase.table("contratos").select("num_contrato, data_fim").execute()
        map_vencimentos = {}
        if res_cont.data:
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
            dia_fixo = int(item['dia_fixo']) if item.get('dia_fixo') is not None else 10
            pular_mes = bool(item.get('pular_mes_atual', False)) if item.get('pular_mes_atual') is not None else False

            inicio_dt = datetime.strptime(inicio_str, "%Y-%m-%d").date()
            data_fatura = calcular_previsao_fat(condicao, inicio_dt, dia_fixo, pular_mes)

            if num_prop in map_vencimentos:
                try:
                    venc_dt = datetime.strptime(map_vencimentos[num_prop], "%Y-%m-%d").date()
                    if data_fatura >= venc_dt:
                        data_fatura = venc_dt
                except Exception:
                    pass

            dias_restantes = (data_fatura - hoje).days

            if dias_restantes == 2 and alerta_enviado < 1:
                assunto = f"[ALERTA OPERACIONAL] Preparação de Faturamento - Proposta Nº {num_prop} ({cliente})"
                corpo = f"Atenção Equipa,\n\nO faturamento para o cliente {cliente} (Proposta Nº {num_prop}) tem data prevista para {data_fatura.strftime('%d/%m/%Y')}.\nFaltam 2 dias para a data limite."
                enviou = False
                for d in lista_destinos:
                    if enviar_email_generico(prov, remetente, senha, d, assunto, corpo):
                        enviou = True
                if enviou:
                    supabase.table("faturamentos").update({"alerta_enviado": 1}).eq("id", rid).execute()
                    try:
                        supabase.table("logs_faturamento").insert({
                            "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "cliente": cliente,
                            "proposta": str(num_prop),
                            "mensagem": f"Assunto: {assunto}\n\n{corpo}",
                            "status": "Enviado com sucesso (Automático BG)"
                        }).execute()
                    except Exception:
                        pass
                    disparos += 1

            elif dias_restantes == 1 and alerta_enviado < 2:
                assunto = f"[ALERTA OPERACIONAL] Véspera de Faturamento - Proposta Nº {num_prop} ({cliente})"
                corpo = f"Atenção Equipa,\n\nO faturamento para o cliente {cliente} (Proposta Nº {num_prop}) tem data prevista para AMANHÃ ({data_fatura.strftime('%d/%m/%Y')})."
                enviou = False
                for d in lista_destinos:
                    if enviar_email_generico(prov, remetente, senha, d, assunto, corpo):
                        enviou = True
                if enviou:
                    supabase.table("faturamentos").update({"alerta_enviado": 2}).eq("id", rid).execute()
                    try:
                        supabase.table("logs_faturamento").insert({
                            "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "cliente": cliente,
                            "proposta": str(num_prop),
                            "mensagem": f"Assunto: {assunto}\n\n{corpo}",
                            "status": "Enviado com sucesso (Automático BG)"
                        }).execute()
                    except Exception:
                        pass
                    disparos += 1

            elif dias_restantes == 0 and alerta_enviado < 3:
                assunto = f"[URGENTE - HOJE] Prazo de Faturamento - Proposta Nº {num_prop} ({cliente})"
                corpo = f"Atenção Equipa,\n\nO faturamento para o cliente {cliente} (Proposta Nº {num_prop}) tem o prazo de entrega PARA HOJE ({data_fatura.strftime('%d/%m/%Y')})."
                enviou = False
                for d in lista_destinos:
                    if enviar_email_generico(prov, remetente, senha, d, assunto, corpo):
                        enviou = True
                if enviou:
                    supabase.table("faturamentos").update({"alerta_enviado": 3}).eq("id", rid).execute()
                    try:
                        supabase.table("logs_faturamento").insert({
                            "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "cliente": cliente,
                            "proposta": str(num_prop),
                            "mensagem": f"Assunto: {assunto}\n\n{corpo}",
                            "status": "Enviado com sucesso (Automático BG)"
                        }).execute()
                    except Exception:
                        pass
                    disparos += 1

        print(f"Automação de Faturamentos concluída. Alertas disparados: {disparos}")
    except Exception as e:
        print(f"Erro na automação de faturamentos: {e}")

if __name__ == "__main__":
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        db = create_client(url, key)
        print("A iniciar rotinas automáticas em segundo plano...")
        rodar_automacao_contratos(db)
        rodar_automacao_faturamentos(db)
        print("Todas as rotinas de background foram executadas com sucesso.")
    else:
        print("Erro: Credenciais do Supabase ausentes nas variáveis de ambiente.")
