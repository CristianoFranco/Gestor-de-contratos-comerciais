import streamlit as st
import pandas as pd
import base64
import os
from datetime import datetime
from supabase import create_client, Client
from modulo_cadastro import renderizar_aba_cadastro
from modulo_propostas import renderizar_aba_propostas
from modulo_proposta_cliente import renderizar_aba_proposta_cliente
from modulo_simulador import renderizar_aba_simulacao

# ==============================================================================
# 1. ESTILO E CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Globex Multimodal - Módulo Comercial",
    page_icon="📦",
    layout="wide"
)

UNIDADES_PADRAO = [
    "",
    "Por caixa",
    "por unidade",
    "por pallet",
    "por hora/homem",
    "por etiqueta",
    "por volume",
    "por mês"
]

if "lista_unidades" not in st.session_state:
    st.session_state["lista_unidades"] = UNIDADES_PADRAO.copy()
if "form_id" not in st.session_state:
    st.session_state["form_id"] = 0
if "aba_ativa" not in st.session_state:
    st.session_state["aba_ativa"] = "cadastro"

def get_base64_of_bin_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return ""

def aplicar_estilo_personalizado():
    bg_b64 = get_base64_of_bin_file('background.jpg')
    
    if bg_b64:
        bg_style = ".stApp {{ background: linear-gradient(rgba(10, 25, 40, 0.75), rgba(10, 25, 40, 0.75)), url('data:image/jpg;base64,{}') no-repeat center center fixed; background-size: cover; }}".format(bg_b64)
    else:
        bg_style = ".stApp { background-color: #0A2540; }"
        
    css_template = """
        <style>
            {}
            
            .header-container {{
                background: rgba(255, 255, 255, 0.95);
                padding: 20px 30px;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 25px;
            }}
            .header-title {{ color: #0A2540; font-size: 24px; font-weight: 800; margin: 0; }}
            .header-subtitle {{ color: #555; font-size: 14px; margin: 0; }}
            
            div[data-testid="stForm"], div.stExpander, div[data-testid="stDataFrame"] {{
                background: rgba(255, 255, 255, 0.95) !important;
                border-radius: 12px !important;
                padding: 20px !important;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
            }}
            
            label, .stMarkdown label, .stMarkdown p {{ color: #0A2540 !important; font-weight: 700 !important; }}
            h1, h2, h3, h4 {{ color: #FFFFFF !important; text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.8); }}
            
            div.stButton > button {{
                border-radius: 8px !important;
                font-weight: 700 !important;
                transition: all 0.2s ease-in-out;
            }}
            
            div.stButton > button:hover, div.stButton > button:hover p, div.stButton > button:hover span {{
                color: #FFFFFF !important;
            }}
        </style>
    """.format(bg_style)
    
    st.markdown(css_template, unsafe_allow_html=True)

aplicar_estilo_personalizado()

# ==============================================================================
# 2. CONEXÃO COM SUPABASE
# ==============================================================================
@st.cache_resource
def obter_cliente_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

@st.cache_data(ttl=60)
def carregar_dados_cached():
    try:
        supabase = obter_cliente_supabase()
        res = supabase.table("servicos").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df = df.rename(columns={
                "codigo": "Código",
                "descricao": "Descrição",
                "tarifa": "Tarifa (R$)",
                "unidade": "Unidade",
                "categoria": "Categoria",
                "observacoes": "Observações",
                "status": "Status"
            })
            return df
        return pd.DataFrame(columns=["Código", "Descrição", "Tarifa (R$)", "Unidade", "Categoria", "Observações", "Status"])
    except Exception as e:
        st.error(f"Erro ao carregar dados do Supabase: {e}")
        return pd.DataFrame()

def carregar_dados(apenas_ativos=True):
    df = carregar_dados_cached()
    colunas_esperadas = ["Código", "Descrição", "Tarifa (R$)", "Unidade", "Categoria", "Observações", "Status"]
    
    if df.empty:
        df_vazio = pd.DataFrame(columns=colunas_esperadas)
        return df_vazio[colunas_esperadas[:-1]] if apenas_ativos else df_vazio

    if "Status" not in df.columns:
        df["Status"] = "Ativo"
    
    # Tratamento robusto para preencher nulos/vazios como Ativo
    df["Status"] = df["Status"].fillna("Ativo").astype(str).str.strip()
    df.loc[df["Status"] == "", "Status"] = "Ativo"
    
    df["Código"] = df["Código"].astype(str).str.strip()
    
    # Filtra registros temporários antigos com DEL_ ou EDIT_
    df = df[
        ~df["Código"].astype(str).str.startswith("DEL_") & 
        ~df["Código"].astype(str).str.startswith("EDIT_")
    ].copy()

    if apenas_ativos:
        df_ativos = df[df["Status"].str.upper() != "INATIVO"].copy()
        return df_ativos[["Código", "Descrição", "Tarifa (R$)", "Unidade", "Categoria", "Observações"]]
    
    return df

def salvar_dados_completos(df_completo):
    try:
        supabase = obter_cliente_supabase()
        
        df_validos = df_completo[
            ~df_completo["Código"].astype(str).str.startswith("DEL_") & 
            ~df_completo["Código"].astype(str).str.startswith("EDIT_")
        ].copy()

        registros = []
        for _, row in df_validos.iterrows():
            registros.append({
                "codigo": str(row.get("Código", "")).strip(),
                "descricao": str(row.get("Descrição", "")).strip(),
                "tarifa": float(row.get("Tarifa (R$)", 0.0) if str(row.get("Tarifa (R$)", 0.0)).strip() != "" else 0.0),
                "unidade": str(row.get("Unidade", "")).strip(),
                "categoria": str(row.get("Categoria", "")).strip(),
                "observacoes": str(row.get("Observações", "")).strip(),
                "status": str(row.get("Status", "Ativo")).strip()
            })
        
        if registros:
            supabase.table("servicos").upsert(registros, on_conflict="codigo").execute()
            
        carregar_dados_cached.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no Supabase: {e}")
        return False

# ==============================================================================
# FUNÇÕES DE INTEGRAÇÃO COM A TELA 3 (PROPOSTAS SALVAS) - SUPABASE
# ==============================================================================
def salvar_propostas_no_supabase(linhas_proposta):
    try:
        supabase = obter_cliente_supabase()
        num_prop = str(linhas_proposta[0].get("Proposta", "")).strip() if linhas_proposta else ""
        if not num_prop:
            st.error("Número da proposta inválido para salvamento.")
            return False

        supabase.table("propostas").delete().eq("proposta", num_prop).execute()

        novos_registros = []
        for reg in linhas_proposta:
            data_val = reg.get("Data", datetime.now().isoformat())
            if not data_val or str(data_val).strip() == "":
                data_val = datetime.now().isoformat()

            novos_registros.append({
                "proposta": str(reg.get("Proposta", "")).strip(),
                "data": data_val,
                "cliente": str(reg.get("Cliente", "")).strip(),
                "cnpj": str(reg.get("CNPJ", "")).strip(),
                "codigo": str(reg.get("Código", "")).strip(),
                "descricao": str(reg.get("Descrição", "")).strip(),
                "categoria": str(reg.get("Categoria", "")).strip(),
                "unidade": str(reg.get("Unidade", "")).strip(),
                "tarifa": float(reg.get("Tarifa (R$)", 0.0) if str(reg.get("Tarifa (R$)", 0.0)).strip() != "" else 0.0),
                "observacoes": str(reg.get("Observações", "")).strip()
            })

        supabase.table("propostas").insert(novos_registros).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao gravar proposta no Supabase: {e}")
        return False

def carregar_propostas_do_supabase():
    try:
        supabase = obter_cliente_supabase()
        res = supabase.table("propostas").select("*").execute()
        if not res.data:
            return pd.DataFrame(columns=["Proposta", "Data", "Cliente", "CNPJ", "Código", "Descrição", "Categoria", "Unidade", "Tarifa (R$)", "Observações"])
        
        df = pd.DataFrame(res.data)
        df = df.rename(columns={
            "proposta": "Proposta",
            "data": "Data",
            "cliente": "Cliente",
            "cnpj": "CNPJ",
            "codigo": "Código",
            "descricao": "Descrição",
            "categoria": "Categoria",
            "unidade": "Unidade",
            "tarifa": "Tarifa (R$)",
            "observacoes": "Observações"
        })
        return df
    except Exception as e:
        return pd.DataFrame(columns=["Proposta", "Data", "Cliente", "CNPJ", "Código", "Descrição", "Categoria", "Unidade", "Tarifa (R$)", "Observações"])

def obter_proximo_numero_proposta_global():
    if st.session_state.get("proposta_id_em_edicao"):
        return st.session_state["proposta_id_em_edicao"]
        
    agora = datetime.now()
    mes = agora.strftime("%m")
    ano = agora.strftime("%Y")
    prefixo_busca = f"{mes}/"
    sufixo_busca = f"/{ano}"
    
    try:
        df_hist = carregar_propostas_do_supabase()
        maior_seq = 0
        if not df_hist.empty and "Proposta" in df_hist.columns:
            for prop in df_hist["Proposta"].dropna().unique():
                p_str = str(prop).strip()
                if p_str.startswith(prefixo_busca) and p_str.endswith(sufixo_busca):
                    partes = p_str.split("/")
                    if len(partes) == 3:
                        try:
                            num_seq = int(partes[1])
                            if num_seq > maior_seq:
                                maior_seq = num_seq
                        except ValueError:
                            continue
        proximo_seq = maior_seq + 1
        return f"{mes}/{proximo_seq:05d}/{ano}"
    except Exception:
        return f"{mes}/00001/{ano}"

def normalizar_codigo(codigo_str):
    limpo = str(codigo_str).strip().upper()
    return str(int(limpo)) if limpo.isdigit() else limpo

def formatar_tarifa(val):
    try:
        f = float(val)
        s = f"{f:.5f}".rstrip('0')
        if s.endswith('.'): s += '00'
        elif len(s.split('.')[1]) < 2: s += '0'
        return s
    except (ValueError, TypeError):
        return str(val)

def executar_renderizar_cadastro():
    params = [carregar_dados, salvar_dados_completos, normalizar_codigo, formatar_tarifa]
    for i in range(len(params), 0, -1):
        try:
            renderizar_aba_cadastro(*params[:i])
            return
        except TypeError:
            continue

# ==============================================================================
# 3. CABEÇALHO & NAVEGAÇÃO
# ==============================================================================
logo_b64 = get_base64_of_bin_file('logo.png')
if logo_b64:
    header_html = """
        <div class="header-container">
            <div>
                <h1 class="header-title">Módulo Comercial & Precificação</h1>
                <p class="header-subtitle">Gestão Integrada de Serviços e Tabelas Tarifárias</p>
            </div>
            <div>
                <img src="data:image/png;base64,{}" style="height: 60px;">
            </div>
        </div>
    """.format(logo_b64)
    st.markdown(header_html, unsafe_allow_html=True)
else:
    st.markdown("""
        <div class="header-container">
            <div>
                <h1 class="header-title">Módulo Comercial & Precificação</h1>
                <p class="header-subtitle">Gestão Integrada de Serviços e Tabelas Tarifárias</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

# BARRA DE NAVEGAÇÃO COM CONTROLE EXCLUSIVO DE ESTADO ATIVO (4 TELAS)
col_nav1, col_nav2, col_nav3, col_nav4, _ = st.columns([2.0, 2.3, 2.3, 2.2, 1.2])
aba_atual = st.session_state["aba_ativa"]

with col_nav1:
    tipo_btn1 = "primary" if aba_atual == "cadastro" else "secondary"
    if st.button("📋 Cadastro", key="btn_nav_cadastro", type=tipo_btn1, use_container_width=True):
        st.session_state["aba_ativa"] = "cadastro"
        st.rerun()

with col_nav2:
    tipo_btn2 = "primary" if aba_atual == "propostas" else "secondary"
    if st.button("🛠️ Proposta Rascunho", key="btn_nav_propostas", type=tipo_btn2, use_container_width=True):
        st.session_state["aba_ativa"] = "propostas"
        st.rerun()

with col_nav3:
    tipo_btn3 = "primary" if aba_atual == "cliente" else "secondary"
    if st.button("📄 Proposta Cliente", key="btn_nav_cliente", type=tipo_btn3, use_container_width=True):
        st.session_state["aba_ativa"] = "cliente"
        st.rerun()

with col_nav4:
    tipo_btn4 = "primary" if aba_atual == "simulacao" else "secondary"
    if st.button("📊 Simulação", key="btn_nav_simulacao", type=tipo_btn4, use_container_width=True):
        st.session_state["aba_ativa"] = "simulacao"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

st.markdown(
    "<script>setTimeout(function() { window.scrollTo({top: 0, behavior: 'auto'}); var mainContent = window.parent.document.querySelector('.main'); if (mainContent) { mainContent.scrollTop = 0; } }, 30);</script>",
    unsafe_allow_html=True
)

if st.session_state["aba_ativa"] == "cadastro":
    executar_renderizar_cadastro()
elif st.session_state["aba_ativa"] == "propostas":
    renderizar_aba_propostas(
        carregar_dados_fn=carregar_dados, 
        salvar_dados_completos_fn=salvar_dados_completos,
        obter_proximo_numero_fn=obter_proximo_numero_proposta_global
    )
elif st.session_state["aba_ativa"] == "cliente":
    renderizar_aba_proposta_cliente(
        salvar_proposta_supabase_fn=salvar_propostas_no_supabase,
        carregar_propostas_supabase_fn=carregar_propostas_do_supabase,
        obter_proximo_numero_fn=obter_proximo_numero_proposta_global
    )
else:
    renderizar_aba_simulacao(
        carregar_dados_fn=carregar_dados,
        carregar_propostas_salvas_fn=carregar_propostas_do_supabase
    )
