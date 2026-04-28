import streamlit as st
import pandas as pd
import os
import uuid
import base64
import requests
from datetime import datetime, time
import streamlit as st
from datetime import datetime, timedelta
from streamlit_cookies_manager import EncryptedCookieManager
import streamlit as st
from supabase import create_client
from passlib.hash import pbkdf2_sha256
import pytz
import hashlib
from supabase import create_client
import pandas as pd

def gerar_hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()

def formatar_data_brasilia(data_utc):
    if not data_utc:
        return ""
    try:
        # Tira o 'Z' ou '+00:00' e entende como UTC
        data_obj = datetime.fromisoformat(str(data_utc).replace('Z', '+00:00'))
        fuso_br = pytz.timezone('America/Sao_Paulo')
        # Converte para o nosso horário
        return data_obj.astimezone(fuso_br).strftime('%d/%m/%Y %H:%M')
    except:
        return data_utc

    
def gerar_hash(senha):
    return pbkdf2_sha256.hash(senha)
    
def carregar_vinculos():
    try:
        res = supabase.table("vinculos").select("*").execute()
        vinc_dict = {}
        for r in res.data:
            # Forçamos para string para garantir o match com o input da tela
            l = str(r['lider']).strip()
            ld = str(r['liderado']).strip()
            
            if l not in vinc_dict:
                vinc_dict[l] = []
            vinc_dict[l].append(ld)
        return vinc_dict
    except Exception as e:
        return {}

@st.cache_data(ttl=2)
def carregar_ocorrencias():
    try:
        res = supabase.table("ocorrencias").select("*").order("id", desc=True).execute()

        dados = res.data if res.data else []

        # garante que id sempre seja inteiro
        for o in dados:
            try:
                o["id"] = int(o.get("id", 0))
            except:
                o["id"] = 0

        return dados

    except Exception as e:
        st.error(f"Erro ao carregar ocorrências do banco: {e}")
        return []
    
def subir_para_storage(arquivo_streamlit):
    """Sobe o arquivo para o Supabase e retorna a URL pública."""
    try:
        # Nome único para o arquivo não sobrescrever outros
        nome_arquivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{arquivo_streamlit.name}"
        caminho_no_bucket = f"atestados/{nome_arquivo}"
        
        # Faz o upload (Certifique-se de ter criado o bucket 'anexos' no Supabase)
        arquivo_bytes = arquivo_streamlit.getvalue()
        supabase.storage.from_("anexos").upload(caminho_no_bucket, arquivo_bytes)
        
        # Gera a URL pública para salvar na tabela
        url_publica = supabase.storage.from_("anexos").get_public_url(caminho_no_bucket)
        return url_publica
    except Exception as e:
        st.error(f"Erro no upload do arquivo: {e}")
        return None



def verificar_senha(senha_digitada, hash_salvo):
    try:
        return pbkdf2_sha256.verify(senha_digitada, hash_salvo)
    except Exception:
        return False
    
# conexão com Supabase
SUPABASE_URL = "https://zedgyvekirmsqvstqvjt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplZGd5dmVraXJtc3F2c3Rxdmp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjY3ODQ3OCwiZXhwIjoyMDg4MjU0NDc4fQ.sAtQhOTjjB1OhSxT6IRG3CNr1FDAdP8Tm_zqcAeo8pI"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


supabase_admin = create_client(SUPABASE_URL, SUPABASE_KEY)

def registrar_log(id_ocorrencia, acao):
    """Gera um rastro de auditoria para cada ação na ocorrência."""
    try:
        # Pega dados do usuário que está logado e realizando a ação
        user_logado = st.session_state.usuario_logado
        
        log_data = {
            "ocorrencia_id": str(id_ocorrencia),
            "quem_fez": f"{user_logado['nome']} ({user_logado['cargo']})",
            "acao": acao,
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }
        
        supabase.table("logs_atividades").insert(log_data).execute()
    except Exception as e:
        st.error(f"Erro ao registrar log de auditoria: {e}")

# FUNÇÃO PARA CARREGAR USUÁRIOS
def carregar_usuarios():
    response = supabase.table("usuarios").select("*").execute()
    return response.data

def criar_gestor_maximo_final(nome_completo, matricula_pura, senha_limpa):
    try:
        # 1. Gerar o hash da senha (que vai na coluna 'matrícula')
        senha_criptografada = pbkdf2_sha256.hash(senha_limpa)
        
        # 2. Formatar a matrícula (que vai na coluna 'e-mail')
        email_formatado = f"{matricula_pura}@rh12.com"
        
        # 3. Montar o dicionário exatamente com as colunas do print
        dados_usuario = {
            "nome": nome_completo,
            "e-mail": email_formatado,
            "matrícula": senha_criptografada, # No seu banco, senha = matrícula
            "carga": "Gestor Máximo",         # No seu banco, cargo = carga
            "Ótimo": "SEDE"                   # Coluna que armazena a unidade/setor
        }
        
        # IMPORTANTE: Verifique se no Supabase a tabela tem acento 'usuários'
        # Se der erro, tente mudar para 'usuarios' (sem acento)
        res = supabase.table("usuários").insert(dados_usuario).execute()
        
        st.success(f"✅ Gestor {nome_completo} criado!")
        return res.data
        
    except Exception as e:
        # Se ainda der erro de 'column not found', vamos imprimir o erro real
        st.error(f"Erro detalhado: {e}")
        return None
        
# 🔹 INICIALIZA A LISTA DE USUÁRIOS
if "db_usuarios" not in st.session_state:
    st.session_state.db_usuarios = carregar_usuarios()

def remover_funcionario_da_unidade(email_func):
    try:
        lider_email = st.session_state.usuario_logado['email']

        # 1. Remove vínculo lider-liderado no banco
        supabase.table("vinculos")\
            .delete()\
            .eq("lider", lider_email)\
            .eq("liderado", email_func)\
            .execute()

        # 2. Atualiza unidade do usuário para nulo no banco
        supabase.table("usuarios")\
            .update({"unidade": None})\
            .eq("email", email_func)\
            .execute()

        # 3. ATUALIZAÇÃO LOCAL (O segredo para não dar erro de interface)
        # Remove a unidade da lista de usuários que já está carregada na memória
        if "db_usuarios" in st.session_state:
            for u in st.session_state.db_usuarios:
                if u['email'] == email_func:
                    u['unidade'] = None
        
        return True
    except Exception as e:
        st.error(f"Erro ao remover vínculo: {e}")
        return False

    # Atualiza memória local para refletir a mudança
    for u in st.session_state.db_usuarios:
        if u['email'] == email_func:
            u['unidade'] = None
            
# 3. >>> COLOQUE AQUI AS INICIALIZAÇÕES <<<
if "funcionario_para_remover" not in st.session_state:
    st.session_state.funcionario_para_remover = None

if "unidade_para_remover" not in st.session_state:
    st.session_state.unidade_para_remover = None

if "rerun_needed" not in st.session_state:
    st.session_state.rerun_needed = False

if "db_usuarios" not in st.session_state:
    st.session_state.db_usuarios = carregar_usuarios()

# RESTAURA LOGIN DO SUPABASE
if "supabase_session" in st.session_state:
        supabase.auth.set_session(
            st.session_state.supabase_session.access_token,
            st.session_state.supabase_session.refresh_token
        )




print(gerar_hash("suasenha"))

# recarrega usuários
st.session_state.db_usuarios = carregar_usuarios()

    

def salvar_csv(nome_arquivo, dados):
    pd.DataFrame(dados).to_csv(nome_arquivo, index=False)
    
@st.cache_data(ttl=2)
def carregar_pendentes(unidade):
    try:
        res = supabase.table("ocorrencias") \
            .select("*") \
            .eq("status", "⏳ Pendente") \
            .eq("unidade", unidade) \
            .order("id", desc=True) \
            .execute()

        return res.data if res.data else []
    except Exception as e:
        st.error(f"Erro ao carregar pendentes: {e}")
        return []


@st.cache_data(ttl=2)
def carregar_minhas_ocorrencias(email):
    try:
        res = supabase.table("ocorrencias") \
            .select("*") \
            .eq("email_solicitante", email) \
            .order("id", desc=True) \
            .execute()

        return res.data if res.data else []
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return []




# ---------------- CONFIG ----------------
LOGIN_EXPIRY_MIN = 1

cookies = EncryptedCookieManager(
    prefix="rh_app",
    password="uma_senha_super_secreta_aqui"
)

if not cookies.ready():
    st.stop()

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None

if "db_ocorrencias" not in st.session_state:
    st.session_state.db_ocorrencias = []


# ----------------------------------------------
# ----------------------------------------------
# ---- Verifica se existe cookie válido ----
if cookies.get("usuario") and cookies.get("login_time"):
    login_time = datetime.fromisoformat(cookies["login_time"])
    
    if datetime.now() - login_time <= timedelta(minutes=LOGIN_EXPIRY_MIN):
        email_cookie = cookies["usuario"]
        user = next((u for u in st.session_state.db_usuarios if u["email"] == email_cookie), None)
        
        if user:
            st.session_state.autenticado = True
            st.session_state.usuario_logado = user
    


# ----------------------------------------------
# ----------------------------------------------
def exibir_anexo(url):
    if not url:
        st.warning("Nenhum anexo disponível.")
        return

    # Em vez de tentar mostrar aqui dentro, damos o botão para abrir fora
    st.link_button("📂 Abrir Documento em Nova Aba", url, use_container_width=True)

def formatar_status(status):
    cores = {
        "⏳ Pendente": "orange",
        "✅ Aprovado": "green",
        "❌ Negado": "red"
    }
    cor = cores.get(status, "gray")
    return f":{cor}[{status}]"

def cor_status(texto):
    if "Pendente" in texto: return "orange"
    if "Aprovado" in texto: return "green"
    if "Negado" in texto: return "red"
    return "gray"

# --------------------------------------------------
# 1. CONFIGURAÇÃO E PASTAS
# --------------------------------------------------
st.set_page_config(page_title="RH Digital - FSPSS", layout="wide")

ARQUIVOS = {
    "ocorrencias": "banco_ocorrencias.csv",
    "vinculos": "banco_vinculos.csv"
}
PASTA_ANEXOS = "anexos"

if not os.path.exists(PASTA_ANEXOS):
    os.makedirs(PASTA_ANEXOS)

# --------------------------------------------------
# 2. FUNÇÕES DE DADOS
# --------------------------------------------------
def salvar_anexo(arquivo_subido, id_ocorrencia):
    if arquivo_subido is not None:
        ext = os.path.splitext(arquivo_subido.name)[1]
        nome_arquivo = f"anexo_{id_ocorrencia}{ext}"
        caminho_completo = os.path.join(PASTA_ANEXOS, nome_arquivo)
        with open(caminho_completo, "wb") as f:
            f.write(arquivo_subido.getbuffer())
        return caminho_completo
    return ""

def carregar_csv(arquivo):
    if os.path.exists(arquivo):
        try:
            df = pd.read_csv(arquivo, dtype=str)
            return df.fillna("").to_dict(orient="records")
        except:
            return []
    return []

def salvar_csv(arquivo, dados):
    pd.DataFrame(dados).to_csv(arquivo, index=False)




# --------------------------------------------------
# 3. INICIALIZAÇÃO (SESSION STATE)
# --------------------------------------------------
if 'db_ocorrencias' not in st.session_state:
    st.session_state.db_ocorrencias = carregar_csv(ARQUIVOS["ocorrencias"])

# Garante que todos tenham 'arquivado'
for item in st.session_state.db_ocorrencias:
    if "arquivado" not in item:
        item["arquivado"] = "Não"
df_oc = pd.DataFrame(st.session_state.db_ocorrencias)
if "arquivado" not in df_oc.columns:
    df_oc["arquivado"] = "Não"
df_arq = df_oc[df_oc["arquivado"] == "Sim"]

for chave, path in ARQUIVOS.items():
    if f'db_{chave}' not in st.session_state:
        st.session_state[f'db_{chave}'] = carregar_csv(path)

if 'vinculos' not in st.session_state:
    st.session_state.vinculos = carregar_vinculos()

# --------------------------------------------------
# 4. AUTENTICAÇÃO
# --------------------------------------------------
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None

from datetime import datetime, timedelta

# Tempo de expiração do login (em minutos)
LOGIN_EXPIRY_MIN = 10

# Verifica se o usuário está logado e se a sessão ainda é válida
if st.session_state.get("autenticado", False):
    login_time = st.session_state.get("login_time", None)
    if login_time:
        if datetime.now() - login_time > timedelta(minutes=LOGIN_EXPIRY_MIN):
            st.session_state.autenticado = False
            st.session_state.usuario_logado = None
            st.warning("Sessão expirada. Faça login novamente.")

# Se não está autenticado, mostra a tela de login
import json
import os
from datetime import datetime, timedelta
import streamlit as st

# --- Configurações ---
LOGIN_EXPIRY_MIN = 10
LOGIN_TEMP_FILE = "login_temp.json"  # arquivo que vai guardar login temporário

# --- Função para carregar login salvo ---
def carregar_login():
    if os.path.exists(LOGIN_TEMP_FILE):
        try:
            with open(LOGIN_TEMP_FILE, "r") as f:
                data = json.load(f)
            login_time = datetime.fromisoformat(data["login_time"])
            if datetime.now() - login_time <= timedelta(minutes=LOGIN_EXPIRY_MIN):
                return data["email"]
        except:
            pass
    return None

# --- Função para salvar login ---
def salvar_login(email):
    with open(LOGIN_TEMP_FILE, "w") as f:
        json.dump({"email": email, "login_time": datetime.now().isoformat()}, f)

# --- Função para remover login ---
def apagar_login():
    if os.path.exists(LOGIN_TEMP_FILE):
        os.remove(LOGIN_TEMP_FILE)

# --- Inicializa session_state ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None

# --- Checa se existe login válido no arquivo ---
# tenta carregar login salvo
email_temp = carregar_login()

if email_temp:
    # busca usuário na memória
    user = next((u for u in st.session_state.db_usuarios if u["email"] == email_temp), None)

    if user:
        st.session_state.autenticado = True
        st.session_state.usuario_logado = user


# --------------------------------------------------
# TELA DE LOGIN
# --------------------------------------------------
if not st.session_state.get("autenticado", False):
    
    # Use isso apenas uma vez para criar o acesso, depois apague o bloco

  

    _, col_login, _ = st.columns([1, 1.5, 1])

    with col_login:
        if st.button("Criar Usuário Administrador Agora"):
            criar_gestor_maximo_final("ADMINISTRADOR", "100", "senha123")
        
        

        st.write("# 🔐 RH Digital - FSPSS")

        with st.container(border=True):

            st.subheader("Acesso ao Sistema")

            e_in = st.text_input("Matrícula")
            s_in = st.text_input("Senha", type="password")

            if st.button("Entrar", use_container_width=True):

                email_login = f"{str(e_in).strip().lower()}@rh12.com"
                senha_login = s_in

                try:
                    # 1️⃣ Login no Supabase Auth
                    auth_resposta = supabase.auth.sign_in_with_password({
                        "email": email_login,
                        "password": senha_login
                    })

                    # 2️⃣ Verifica autenticação
                    if auth_resposta.user:

                        # salva sessão do supabase
                        st.session_state.supabase_session = auth_resposta.session

                        user_id = auth_resposta.user.id

                        # 3️⃣ Busca usuário na tabela usuarios
                        usuario_res = supabase.table("usuarios") \
                            .select("*") \
                            .eq("email", email_login) \
                            .execute()

                        if usuario_res.data:

                            usuario = usuario_res.data[0]

                            # salva sessão
                            st.session_state.usuario_logado = usuario
                            st.session_state.autenticado = True
                            st.session_state.login_time = datetime.now()

                            salvar_login(email_login)

                            st.success(f"✅ Bem-vindo, {usuario['nome']}!")
                            st.rerun()

                        else:
                            st.error("Usuário não encontrado na tabela.")

                    else:
                        st.error("Email ou senha inválidos.")

                except Exception as e:
                    # Transformamos o erro técnico em uma mensagem amigável
                    erro_msg = str(e)
                    
                    if "Invalid login credentials" in erro_msg:
                        st.error("❌ Matrícula ou senha incorretos. Tente novamente.")
                    elif "network" in erro_msg.lower():
                        st.error("🌐 Erro de conexão. Verifique sua internet.")
                    else:
                        # Para qualquer outro erro, mostramos algo genérico sem expor o código
                        st.error("⚠️ Não foi possível acessar o sistema no momento.")
                    
                    # Opcional: print(f"DEBUG: {erro_msg}") # Isso só


# --------------------------------------------------
# TRAVA DE SEGURANÇA
# --------------------------------------------------
if not st.session_state.get("autenticado", False) or st.session_state.get("usuario_logado") is None:
    st.stop()


# --------------------------------------------------
# USUÁRIO LOGADO
# --------------------------------------------------
user = st.session_state.usuario_logado
email_logado = user['email']

# garante que os dados do banco carreguem
if st.session_state.autenticado:
    try:
        st.session_state.db_ocorrencias = carregar_ocorrencias()
    except:
        st.session_state.db_ocorrencias = []


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------
if st.sidebar.button("🚪 Sair", key="logout_btn"):

    # limpa sessão
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None

    # remove login salvo
    apagar_login()

    # limpa cookies (se existir)
    if 'cookies' in locals():
        cookies["usuario"] = ""
        cookies["login_time"] = ""
        cookies.save()

    st.rerun()


# --------------------------------------------------
# TELA PRINCIPAL
# --------------------------------------------------
st.title(f"Olá, {user['nome']}!")

# --------------------------------------------------
# 5. PAINEL GESTOR MÁXIMO (ADMIN COMPLETO)
# --------------------------------------------------
if user['cargo'] == "Gestor Máximo":
    st.header("Painel Administrativo Central")
    t_users, t_vinc, t_aprovar, t_hist, t_arq, t_rel = st.tabs([
        "👥 Equipe", 
        "🔗 Vínculos", 
        "✅ Aprovar Folgas",
        "📊 Monitoramento", 
        "📦 Arquivo Morto",
        "📈 Relatórios"
    ])
    with t_users:
        # 1. FORMULÁRIO DE CADASTRO
        with st.expander("➕ Novo Usuário"):
            with st.form("cad_u", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n_n = c1.text_input("Nome completo")
                n_m = c2.text_input("Senha (mín. 6 caracteres)", type="password")
                n_e = c1.text_input("Matrícula (Login)")
                n_c = c2.selectbox("Cargo", ["Funcionário", "Enfermeiro", "Supervisor", "Gestor Máximo"])
                
                if st.form_submit_button("Salvar Usuário"):
                    if len(str(n_m).strip()) < 6:
                        st.error("🔒 A senha deve ter no mínimo 6 caracteres.")
                    elif not n_e or not n_n:
                        st.warning("⚠️ Preencha Nome e Matrícula.")
                    else:
                        email_interno = f"{n_e}@rh12.com"
                        senha_hash = gerar_hash(n_m)
    
                        novo_usuario = {
                            "email": email_interno,
                            "nome": n_n,
                            "cargo": n_c,
                            "matricula": senha_hash  # Armazenando o hash da senha
                        }
                    
                        try:
                            # 1. Cria no Auth do Supabase
                            supabase.auth.sign_up({
                                "email": email_interno,
                                "password": n_m
                            })
                            
                            # 2. Salva na tabela pública de usuários
                            supabase.table("usuarios").insert(novo_usuario).execute()
                            
                            # Atualiza estado e recarrega
                            st.session_state.db_usuarios = carregar_usuarios() 
                            st.success(f"Usuário {n_n} cadastrado com sucesso!")
                            st.rerun()
                    
                        except Exception as e:
                            st.error(f"Erro ao salvar no banco: {e}")
    
        st.divider()
    
        # 2. LISTAGEM E PESQUISA
        busca = st.text_input("🔍 Pesquisar por nome ou matrícula", placeholder="Digite para filtrar...")
        
        # Filtro da lista baseada na busca
        usuarios_filtrados = [
            u for u in st.session_state.db_usuarios 
            if busca.lower() in u['nome'].lower() or busca in str(u.get('email', ''))
        ]
            
        for u in usuarios_filtrados:
                    # Evita que o usuário logado se auto-exclua ou edite (opcional)
                    if u['email'] == st.session_state.usuario_logado.get('email'): 
                        continue
                        
                    with st.expander(f"👤 {u['nome']} — {u['cargo']}"):
                        pode_editar = st.session_state.usuario_logado.get("cargo") == "Gestor Máximo"
                        
                        col1, col2 = st.columns(2)
                        
                        # USANDO u['id'] EM TODAS AS KEYS PARA EVITAR DUPLICIDADE
                        edit_nome = col1.text_input("Nome", value=u["nome"], key=f"nome_edit_{u['id']}", disabled=not pode_editar)
                        
                        matrícula_atual = u["email"].split("@")[0]
                        edit_matricula = col2.text_input("Matrícula", value=matrícula_atual, key=f"mat_edit_{u['id']}", disabled=not pode_editar)
                        
                        edit_senha = col1.text_input("Alterar Senha", type="password", key=f"pass_edit_{u['id']}", disabled=not pode_editar)
                        
                        # CORREÇÃO DA KEY DO SELECTBOX
                        edit_cargo = col2.selectbox(
                            "Cargo",
                            ["Funcionário", "Enfermeiro", "Supervisor", "Gestor Máximo"],
                            index=["Funcionário", "Enfermeiro", "Supervisor", "Gestor Máximo"].index(u['cargo']),
                            key=f"cargo_edit_{u['id']}", # <-- Mudado de c_{u['email']} para usar o ID
                            disabled=not pode_editar
                        )
        
                        btn_update, btn_delete = st.columns(2)
                            
                        if btn_update.button("💾 Salvar Alterações", key=f"btn_up_{u['id']}"):
                            try:
                                # 1. Definições de e-mail (O antigo que está no objeto 'u' e o novo do input)
                                email_atual_no_auth = str(u["email"]).strip().lower() 
                                novo_email = f"{str(edit_matricula).strip()}@rh12.com"
                        
                                # 2. Busca o usuário no Auth para pegar o UUID (id interno do Supabase)
                                res_auth = supabase_admin.auth.admin.list_users()
                                users_data = getattr(res_auth, 'users', res_auth) if not isinstance(res_auth, list) else res_auth
                                
                                # Procuramos o usuário pelo e-mail que ele TINHA antes da edição
                                target_auth_user = next((user for user in users_data if user.email.lower() == email_atual_no_auth), None)
                        
                                if target_auth_user:
                                    # --- PASSO A: ATUALIZAR O AUTH PRIMEIRO ---
                                    auth_updates = {"email": novo_email}
                                    if edit_senha:
                                        auth_updates["password"] = str(edit_senha)
                                    
                                    # Usamos o ID do Auth (UUID) para não ter erro de e-mail duplicado ou não achado
                                    supabase_admin.auth.admin.update_user_by_id(target_auth_user.id, attributes=auth_updates)
                        
                                    # --- PASSO B: ATUALIZAR A TABELA 'usuarios' ---
                                    dados_tabela = {
                                        "nome": str(edit_nome).strip(),
                                        "email": novo_email,
                                        "cargo": str(edit_cargo).strip()
                                    }
                                    if edit_senha:
                                        dados_tabela["matricula"] = gerar_hash(str(edit_senha))
                        
                                    # Atualiza no banco usando o ID da linha
                                    supabase.table("usuarios").update(dados_tabela).eq("id", u['id']).execute()
                                    
                                    st.success("✅ Login (Auth) e Banco de Dados atualizados com sucesso!")
                                else:
                                    st.error(f"❌ Erro: O usuário '{email_atual_no_auth}' não existe no Authentication.")
                        
                                st.session_state.db_usuarios = carregar_usuarios()
                                st.rerun()
                        
                            except Exception as e:
                                st.error(f"Erro ao sincronizar: {e}")

                        # BOTÃO EXCLUIR
                        if btn_delete.button("🗑️ Excluir Usuário", key=f"btn_del_{u['id']}"):
                            try:
                                email_para_deletar = str(u["email"]).strip().lower()
                                
                                # 1. Busca o UUID no Auth para garantir a exclusão correta
                                res_auth = supabase_admin.auth.admin.list_users()
                                users_data = getattr(res_auth, 'users', res_auth) if not isinstance(res_auth, list) else res_auth
                                
                                target_auth_user = next((user for user in users_data if user.email.lower() == email_para_deletar), None)
        
                                # 2. Se o usuário existe no Auth, deleta lá primeiro
                                if target_auth_user:
                                    supabase_admin.auth.admin.delete_user(target_auth_user.id)
                                
                                # 3. Deleta da tabela pública de usuários (usando o ID único)
                                supabase.table("usuarios").delete().eq("id", u['id']).execute()
                                
                                st.success(f"✅ Usuário {u['nome']} removido do sistema e do Login!")
                                
                                # Atualiza a lista e recarrega a página
                                st.session_state.db_usuarios = carregar_usuarios()
                                st.rerun()
        
                            except Exception as e:
                                st.error(f"Erro ao excluir usuário: {e}")
                                
    with t_vinc:
        st.subheader("🏢 Gestão de Unidades e Equipes")
    
        # --- PARTE 1: Criar nova unidade ---
        nova_unidade_key = f"cadastro_unidade_form_{st.session_state.get('form_counter', 0)}"
        
        with st.expander("➕ Criar Nova Unidade/Setor", expanded=False):
            with st.form(nova_unidade_key):
                nova_unidade = st.text_input("Nome da Unidade (ex: USF Boiçucanga, Administrativo):")
                if st.form_submit_button("Cadastrar Unidade"):
                    if nova_unidade:
                        try:
                            supabase.table("unidades").insert({"nome": nova_unidade}).execute()
                            st.success("Unidade criada!")
                            # Incrementa contador para próxima vez
                            st.session_state["form_counter"] = st.session_state.get("form_counter", 0) + 1
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Erro ao criar: {e}")
                    else:
                        st.warning("Digite um nome para a unidade.")
    
        # --- Carrega unidades do banco ---
        res_unidades = supabase.table("unidades").select("*").execute()
        unidades_db = res_unidades.data if res_unidades.data else []
    
        if unidades_db:
            st.markdown("---")
            st.markdown("### 🔗 Alocar Funcionários em Unidade")
    
            nomes_unidades = [u['nome'] for u in unidades_db]
            unidade_nome_sel = st.selectbox("Selecione a Unidade destino:", [""] + nomes_unidades)
    
            unidade_selecionada = next((u for u in unidades_db if u['nome'] == unidade_nome_sel), None)
    
            if unidade_selecionada:
                st.markdown(f"#### 👥 Equipe para: {unidade_selecionada['nome']}")
    
                todos_users = [u['email'] for u in st.session_state.db_usuarios]
    
                u_func = st.multiselect(
                    "Selecionar Funcionários para alocar:",
                    todos_users,
                    format_func=lambda x: next(u['nome'] for u in st.session_state.db_usuarios if u['email'] == x)
                )
    
                if st.button("Confirmar Alocação", use_container_width=True):
                    if not u_func:
                        st.warning("Selecione pelo menos um funcionário.")
                    else:
                        try:
                            lider_email = st.session_state.usuario_logado['email']
                            for email in u_func:
                                supabase.table("vinculos").insert({
                                    "lider": lider_email,
                                    "liderado": email
                                }).execute()
    
                                supabase.table("usuarios").update({
                                    "unidade": unidade_selecionada['nome']
                                }).eq("email", email).execute()
    
                            for u in st.session_state.db_usuarios:
                                if u['email'] in u_func:
                                    u['unidade'] = unidade_selecionada['nome']
    
                            st.success(f"Funcionários alocados com sucesso em {unidade_selecionada['nome']}!")
                            st.session_state.rerun_needed = True
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
    
        # --- PARTE 3: Aba de pesquisa de unidades ---
        # --- PARTE 3: Gestão visual das unidades ---
        st.markdown("---")
        st.subheader("🏢 Unidades e Equipes")
        
        pesquisa_unidade = st.text_input("🔎 Buscar unidade", key="pesquisa_unidade")
        
        unidades_filtradas = [
            u for u in unidades_db
            if pesquisa_unidade.lower() in u["nome"].lower()
        ]
        
        if unidades_filtradas:
        
            for uni in unidades_filtradas:
        
                membros = [
                    u for u in st.session_state.db_usuarios
                    if u.get("unidade") == uni["nome"]
                ]
        
                # Expander da unidade
                col_nome, col_del = st.columns([0.9, 0.1])
                
                with col_nome:
                    exp = st.expander(f"📍 {uni['nome']} ({len(membros)} funcionários)")
                
                with col_del:
                    if st.button("🗑️", key=f"del_uni_{uni['id']}", help="Excluir unidade"):
                        try:
                            supabase.table("unidades").delete().eq("id", uni["id"]).execute()
                
                            for u in st.session_state.db_usuarios:
                                if u.get("unidade") == uni["nome"]:
                                    u["unidade"] = None
                
                            st.success("Unidade excluída!")
                            st.session_state.rerun_needed = True
                
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
                
                with exp:
                    st.markdown("---")
                        
                    if membros:
        
                        for m in membros:
        
                            cargo_emoji = "🩺" if m["cargo"] == "Enfermeiro" else "👤"
        
                            col1, col2 = st.columns([0.85, 0.15])
        
                            with col1:
                                st.write(
                                    f"{cargo_emoji} **{m['nome']}** — {m['cargo']}"
                                )
        
                            with col2:
                                if st.button(
                                    "❌",
                                    key=f"remover_{uni['id']}_{m['email']}",
                                    help="Remover da unidade"
                                ):
                                    st.session_state.funcionario_para_remover = m["email"]
                                    st.session_state.unidade_para_remover = uni["nome"]
        
                    else:
                        st.info("Nenhum funcionário nesta unidade.")
        
        else:
            st.info("Nenhuma unidade encontrada.")
    
    # --- Executa ações e rerun fora de loops e containers ---
    if st.session_state.funcionario_para_remover:
        remover_funcionario_da_unidade(st.session_state.funcionario_para_remover)
        st.success(f"{st.session_state.funcionario_para_remover} removido da unidade {st.session_state.unidade_para_remover}.")
    
        # Limpa flags
        st.session_state.funcionario_para_remover = None
        st.session_state.unidade_para_remover = None
    
    
    # --- Rerun seguro para criação/alocação ---
    if st.session_state.get("rerun_needed", False):
        st.session_state["rerun_needed"] = False
        st.rerun()  # <--- MUDOU AQUI!
                
    with t_aprovar:
    
        st.subheader("⚖️ Despacho de Folgas e Abonos")
            
        # Filtra as solicitações que aguardam a Direção
        pendentes = [o for o in st.session_state.db_ocorrencias if o.get("status") == "⏳ Aguardando Direção"]
        
        if not pendentes:
            st.info("Não há solicitações aguardando sua aprovação.")
        else:
            for f in pendentes:
                with st.container(border=True):
                    c_info, c_acts = st.columns([0.7, 0.3])
                    
                    with c_info:
                        st.markdown(f"### 👤 {f['solicitante']}")
                        st.write(f"**Tipo:** {f['motivo']} | **Data:** {f['data']}")
                        st.write(f"**Validado por:** {f.get('aprovado_por', 'Chefia Imediata')}")
                        
                        # --- EXIBIÇÃO DA JUSTIFICATIVA ---
                        if f.get('detalhes'):
                            st.info(f"**Justificativa do Funcionário:**\n\n{f['detalhes']}")
                        else:
                            st.caption("Nenhuma justificativa por escrito foi enviada.")
                        
                        # --- EXIBIÇÃO DO ANEXO ---
                        if f.get('anexo'): # Supondo que sua coluna no Supabase se chame 'anexo_url'
                            st.write("**Documento Anexado:**")
                            # Verifica se é uma imagem ou PDF (ajuste conforme sua necessidade)
                            url = f['anexo']
                            if url.lower().endswith(('.png', '.jpg', '.jpeg')):
                                st.image(url, caption="Comprovante enviado", use_container_width=True)
                            else:
                                st.link_button("📂 Abrir Documento/PDF", url)
                        else:
                            st.warning("⚠️ Nenhum anexo enviado para esta solicitação.")
    
                    with c_acts:
                        st.write("###") # Espaçamento
                        
                        # --- BOTÃO DEFERIR ---
                        if st.button("✅ DEFERIR", key=f"def_{f['id']}", use_container_width=True):
                            try:
                                supabase.table("ocorrencias").update({
                                    "status": "✅ Deferido",
                                    "aprovado_por": f"{f.get('aprovado_por')} / Direção"
                                }).eq("id", f['id']).execute()
    
                                # 1. REGISTRA O LOG
                                registrar_log(f['id'], "Ocorrência DEFERIDA pela Direção")
                                
                                # 2. LIMPA O CACHE E RECARREGA (O segredo para atualizar na hora!)
                                st.cache_data.clear()
                                st.session_state.db_ocorrencias = carregar_ocorrencias()
                                
                                st.success("Solicitação deferida com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao deferir: {e}")
    
                        # --- BOTÃO INDEFERIR ---
                        if st.button("❌ INDEFERIR", key=f"ind_{f['id']}", use_container_width=True):
                            try:
                                supabase.table("ocorrencias").update({
                                    "status": "❌ Indeferido",
                                    "aprovado_por": "Direção"
                                }).eq("id", f['id']).execute()
    
                                # 1. REGISTRA O LOG
                                registrar_log(f['id'], "Ocorrência INDEFERIDA pela Direção")
                                
                                # 2. LIMPA O CACHE E RECARREGA
                                st.cache_data.clear()
                                st.session_state.db_ocorrencias = carregar_ocorrencias()
                                
                                st.warning("Solicitação indeferida.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao indeferir: {e}")
        





    
    with t_hist:
            st.subheader("📊 Monitoramento Geral")
            
            if st.session_state.db_ocorrencias:
                df_oc = pd.DataFrame(st.session_state.db_ocorrencias)
                
                # --- 1. INTERFACE DE FILTROS ---
                with st.container(border=True):
                    f1, f2, f3, f4, f5 = st.columns(5)
                    with f1: f_nome = st.text_input("👤 Nome", placeholder="Buscar...")
                    with f2:
                        opcoes_status = ["Todos"] + sorted(list(df_oc["status"].unique()))
                        f_status = st.selectbox("📌 Status", opcoes_status)
                    with f3:
                        opcoes_motivo = ["Todos", "🎯 Todas as Folgas", "⏰ Todas as Ocorrências"] + sorted(list(df_oc["motivo"].unique()))
                        f_motivo = st.selectbox("💡 Motivo", opcoes_motivo)
                    with f4: f_data_sel = st.date_input("📅 Data", value=None, format="DD/MM/YYYY")
                    with f5: ordem = st.selectbox("⏳ Ordem", ["Mais Recentes", "Mais Antigas"])
    
                # --- 2. LÓGICA DE FILTRAGEM ---
                mask = df_oc["arquivado"] != "Sim"
                if f_nome: mask &= df_oc["solicitante"].str.contains(f_nome, case=False, na=False)
                if f_status != "Todos": mask &= df_oc["status"] == f_status
                
                if f_motivo == "🎯 Todas as Folgas":
                    mask &= df_oc["motivo"].str.contains("Folga", case=False, na=False)
                elif f_motivo == "⏰ Todas as Ocorrências":
                    mask &= ~df_oc["motivo"].str.contains("Folga", case=False, na=False)
                elif f_motivo != "Todos":
                    mask &= df_oc["motivo"] == f_motivo
    
                if f_data_sel:
                    data_str = f_data_sel.strftime("%Y-%m-%d")
                    mask &= df_oc["data"].astype(str).str.contains(data_str, na=False)
    
                df_filtrado = df_oc[mask].copy()
                ordem_asc = (ordem == "Mais Antigas")
                df_filtrado = df_filtrado.sort_values(by="id", ascending=ordem_asc)
    
                # --- 3. EXIBIÇÃO DOS CARDS RECONSTRUÍDOS ---
                if df_filtrado.empty:
                    st.info("Nenhum registro encontrado.")
                else:
                    st.caption(f"🔢 {len(df_filtrado)} registros encontrados")
                    
                    for _, o in df_filtrado.iterrows():
                    
                        # Garantia segura do ID
                        try:
                            id_real = int(o.get("id", 0))
                        except (ValueError, TypeError):
                            continue
                        
                        with st.container(border=True):
                            col_info, col_acao = st.columns([0.8, 0.2])
                            
                            # -- Informações Principais --
                            with col_info:
                                # Tenta usar a cor do status se a função existir
                                try:
                                    status_formatado = f":{cor_status(o['status'])}[**{o['status']}**]"
                                except:
                                    status_formatado = f"**{o['status']}**"
                                    
                                st.markdown(f"### 👤 {o['solicitante']}")
                                st.markdown(f"📅 **Data:** {o['data']} | 💡 **Motivo:** {o['motivo']} | 📌 **Status:** {status_formatado}")
                                
                                if o.get("horarios"):
                                    st.caption(f"🕒 Horários: {o['horarios']}")
                                
                                if "aprovado_por" in o and pd.notna(o["aprovado_por"]) and o["aprovado_por"] != "":
                                    st.markdown(f"✅ **Analisado por:** {o['aprovado_por']}")

                                with st.expander("🕒 Ver Linha do Tempo / Auditoria"):
                                    try:
                                        res_logs = supabase.table("logs_atividades").select("*").eq("ocorrencia_id", str(o['id'])).order("created_at", desc=False).execute()
                                        
                                        if res_logs.data:
                                            for log in res_logs.data:
                                                # 1. Converte o horário do servidor (UTC) para Brasília
                                                data_formatada = formatar_data_brasilia(log['created_at'])
                                                
                                                # 2. Exibe as informações com o horário corrigido
                                                st.caption(f"📅 {data_formatada}")
                                                st.markdown(f"**{log['acao']}**")
                                                st.markdown(f"👤 Responsável: {log['quem_fez']}")
                                                st.divider()
                                        else:
                                            st.info("Sem logs para esta ocorrência.")
                                            
                                    except Exception as e:
                                        st.error(f"Erro ao carregar auditoria: {e}")
    
                                # Justificativa e Anexo (Funcionalidades que tinham sumido)
                                if o.get("detalhes"):
                                    with st.expander("📄 Ver Justificativa Completa"):
                                        st.write(o["detalhes"])
                                
                                if o.get("anexo"):
                                    with st.expander("🖼️ Visualizar Documento"):
                                        exibir_anexo(o["anexo"])
    
                            # -- Botões de Ação Lateral --
                            with col_acao:
                                st.write("") # Alinhamento
                                if st.button("📦 Arquivar", key=f"btn_arq_{id_real}", use_container_width=True):
                                    try:
                                        supabase.table("ocorrencias").update({"arquivado": "Sim"}).eq("id", id_real).execute()
                                        st.cache_data.clear()

                                        # REGISTRA O LOG DO ARQUIVAMENTO
                                        registrar_log(id_real, "Ocorrência enviada para o Arquivo Morto")
                                        
                                        st.session_state.db_ocorrencias = carregar_ocorrencias()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")
    
                                if st.button("🗑️ Excluir", key=f"btn_exc_{id_real}", use_container_width=True):
                                    try:
                                        supabase.table("ocorrencias").delete().eq("id", id_real).execute()
                                        st.cache_data.clear()
                                        st.session_state.db_ocorrencias = carregar_ocorrencias()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")
            else:
                st.info("Sem registros no banco de dados.")

    with t_arq:
        st.subheader("📦 Arquivo Morto - Ocorrências Arquivadas")
    
        if st.session_state.db_ocorrencias:
            df_completo = pd.DataFrame(st.session_state.db_ocorrencias)
    
            # Garante que a coluna 'arquivado' existe
            if "arquivado" not in df_completo.columns:
                df_completo["arquivado"] = "Não"
            else:
                df_completo["arquivado"] = df_completo["arquivado"].fillna("Não").replace("", "Não")
    
            # FILTRA APENAS OS ARQUIVADOS
            df_arq = df_completo[df_completo["arquivado"] == "Sim"]
    
            if not df_arq.empty:
                # --- 1. INTERFACE DE FILTROS ---
                with st.container(border=True):
                    f1, f2, f3, f4, f5 = st.columns(5)
                    with f1: f_nome = st.text_input("👤 Nome", placeholder="Buscar...", key="f_nome_arq")
                    with f2:
                        opcoes_status = ["Todos"] + sorted(list(df_arq["status"].unique()))
                        f_status = st.selectbox("📌 Status", opcoes_status, key="f_status_arq")
                    with f3:
                        opcoes_motivo = ["Todos", "🎯 Todas as Folgas", "⏰ Todas as Ocorrências"] + sorted(list(df_arq["motivo"].unique()))
                        f_motivo = st.selectbox("💡 Motivo", opcoes_motivo, key="f_motivo_arq")
                    with f4: f_data_sel = st.date_input("📅 Data", value=None, format="DD/MM/YYYY", key="f_data_arq")
                    with f5: ordem = st.selectbox("⏳ Ordem", ["Mais Recentes", "Mais Antigas"], key="f_ordem_arq")
    
                # --- 2. LÓGICA DE FILTRO ---
                mask = pd.Series([True] * len(df_arq), index=df_arq.index)
    
                if f_nome:
                    mask &= df_arq["solicitante"].str.contains(f_nome, case=False, na=False)
                if f_status != "Todos":
                    mask &= df_arq["status"] == f_status
    
                if f_motivo == "🎯 Todas as Folgas":
                    mask &= df_arq["motivo"].str.contains("Folga", case=False, na=False)
                elif f_motivo == "⏰ Todas as Ocorrências":
                    mask &= ~df_arq["motivo"].str.contains("Folga", case=False, na=False)
                elif f_motivo != "Todos":
                    mask &= df_arq["motivo"] == f_motivo
    
                if f_data_sel:
                    data_str = f_data_sel.strftime("%Y-%m-%d")
                    mask &= df_arq["data"].astype(str).str.contains(data_str, na=False)
    
                    df_arq_filtrado = df_arq[mask].copy()
                    ordem_asc = (ordem == "Mais Antigas")
                    df_arq_filtrado = df_arq_filtrado.sort_values(by="id", ascending=ordem_asc)
    
                # --- 3. EXIBIÇÃO DOS CARDS ---
                if df_arq_filtrado.empty:
                    st.info("Nenhum registro arquivado encontrado.")
                else:
                    st.caption(f"🔢 {len(df_arq_filtrado)} registros encontrados")
    
                    for _, o in df_arq_filtrado.iterrows():
                        with st.container(border=True):
                            col_info, col_acao = st.columns([0.8, 0.2])
    
                            with col_info:
                                st.markdown(f"👤 **{o['solicitante']}**")
                                st.markdown(f"📅 {o['data']} | 💡 {o['motivo']} | 📌 {o['status']}")
                                if o.get("horarios"):
                                    st.caption(f"🕒 Horários: {o['horarios']}")
                                if "aprovado_por" in o and pd.notna(o["aprovado_por"]) and o["aprovado_por"] != "":
                                    st.markdown(f"✅ **Analisado por:** {o['aprovado_por']}")
                                if o.get("detalhes"):
                                    with st.expander("📄 Justificativa Completa"):
                                        st.write(o["detalhes"])
                                if o.get("anexo"):
                                    with st.expander("🖼️ Visualizar Documento"):
                                        exibir_anexo(o["anexo"])
    
                                with col_acao:
                                    # Mudamos 'id_real' para 'o['id']' que é como o seu loop está definido
                                    if st.button("📤 Restaurar", key=f"rest_{o['id']}", use_container_width=True):
                                        try:
                                            # 1. Atualiza no banco de dados
                                            supabase.table("ocorrencias").update({"arquivado": "Não"}).eq("id", o['id']).execute()
                                            
                                            # 2. Registra a auditoria com o horário de Brasília
                                            registrar_log(o['id'], "Ocorrência restaurada do Arquivo Morto")
                                            
                                            # 3. Atualiza a tela
                                            st.session_state.db_ocorrencias = carregar_ocorrencias()
                                            st.success("Ocorrência restaurada!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Erro ao restaurar: {e}")

                                if st.button("🗑️ Excluir", key=f"del_{o['id']}", use_container_width=True):
                                    try:
                                        # 1. Deleta fisicamente no Supabase
                                        supabase.table("ocorrencias").delete().eq("id", o['id']).execute()
                                        
                                        # 2. LIMPA O CACHE (Essencial para o item sumir da lista na hora)
                                        st.cache_data.clear()
                                        
                                        # 3. Atualiza a memória e recarrega a página
                                        st.session_state.db_ocorrencias = carregar_ocorrencias()
                                        st.success("Ocorrência excluída com sucesso!")
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"Erro ao excluir: {e}")
            else:
                st.info("Nenhum registro arquivado.")
        else:
            st.info("Sem registros no banco de dados.")


    with t_rel:
    
        st.subheader("📈 Relatório Mensal")
    
        if st.button("📊 Gerar relatório do mês"):
    
            import datetime
            from collections import Counter
    
            mes_atual = datetime.datetime.now().month
            ano_atual = datetime.datetime.now().year
    
            ocorrencias = st.session_state.db_ocorrencias
    
            ocorrencias_mes = []
    
            for o in ocorrencias:
                try:
                    data_oc = datetime.datetime.strptime(o["data"], "%Y-%m-%d")
    
                    if data_oc.month == mes_atual and data_oc.year == ano_atual:
                        ocorrencias_mes.append(o)
    
                except:
                    continue
    
            # separação
            folgas = [o for o in ocorrencias_mes if "folga" in o["motivo"].lower()]
            ocorrs = [o for o in ocorrencias_mes if "folga" not in o["motivo"].lower()]
    
            st.markdown("## 🎯 Folgas")
    
            col1, col2, col3 = st.columns(3)
    
            col1.metric("Total", len(folgas))
            col2.metric("Deferidas", len([o for o in folgas if "Deferido" in o["status"]]))
            col3.metric("Pendentes", len([o for o in folgas if "Aguardando" in o["status"]]))
    
            st.markdown("---")
    
            st.markdown("## ⏰ Ocorrências")
    
            col1, col2, col3 = st.columns(3)
    
            col1.metric("Total", len(ocorrs))
            col2.metric("Resolvidas", len([o for o in ocorrs if "Deferido" in o["status"]]))
            col3.metric("Pendentes", len([o for o in ocorrs if "Aguardando" in o["status"]]))
    
            # por unidade
            contagem_unidade = Counter(o.get("unidade", "Sem unidade") for o in ocorrencias_mes)
    
            st.markdown("## 🏢 Registros por unidade")
    
            for unidade, qtd in contagem_unidade.items():
                st.write(f"**{unidade}** — {qtd}")

# --------------------------------------------------
# 6. VISÃO OPERACIONAL (ENFERMEIRO, SUPERVISOR, FUNCIONÁRIO)
# --------------------------------------------------
# --------------------------------------------------
# 6. VISÃO OPERACIONAL (ENFERMEIRO, SUPERVISOR, FUNCIONÁRIO)
# --------------------------------------------------
# --------------------------------------------------
# 6. VISÃO OPERACIONAL (ENFERMEIRO, SUPERVISOR, FUNCIONÁRIO)
# --------------------------------------------------
else:
    # --- LÓGICA DE FILTRAGEM DE PENDÊNCIAS POR UNIDADE ---
    email_logado = st.session_state.usuario_logado.get('email')
    user = st.session_state.usuario_logado 
    minha_unidade = user.get('unidade') # Pega a unidade salva no cadastro do líder

    if user['cargo'] in ["Enfermeiro", "Supervisor"]:

        
        # 2. Filtramos as ocorrências: Devem ser "Pendentes" E o solicitante deve ser da unidade
        res = supabase.table("ocorrencias") \
            .select("*") \
            .eq("status", "⏳ Pendente") \
            .eq("unidade", minha_unidade) \
            .neq("email_solicitante", email_logado) \
            .order("id", desc=True) \
            .execute()
        
        pendentes = res.data if res.data else []
        
        tab_aprov, tab_nova, tab_hist, tab_decididos = st.tabs([
            f"📋 Aprovações ({len(pendentes)})", "📝 Nova ocorrência", "📜 Meu Histórico", "✅ Minhas Decisões"
        ])
        
    elif user['cargo'] == "Gestor Máximo":
        # O Gestor Máximo continua vendo TUDO que está com a direção, independente da unidade
        res = supabase.table("ocorrencias") \
            .select("*") \
            .eq("status", "⏳ Aguardando Direção") \
            .order("id", desc=True) \
            .execute()
        
        pendentes = res.data if res.data else []
        
        tab_aprov, tab_nova, tab_hist, tab_decididos = st.tabs([
            f"🏛️ Decisão Final ({len(pendentes)})", "📝 Nova ocorrência", "📜 Meu Histórico", "✅ Minhas Decisões"
        ])
        
    else:
        tab_nova, tab_hist = st.tabs(["📝 Nova ocorrência", "📜 Meu Histórico"])
        tab_aprov = None
        tab_decididos = None

    # ---------------- TAB APROVAÇÕES (Lógica Dupla) ----------------
    if tab_aprov:
        with tab_aprov:
            st.header("📋 Gestão de Ocorrências")
            
            if not pendentes:
                st.info("Nada pendente para sua análise no momento.")
            else:
                for oc in pendentes:
                    with st.container(border=True):
                        c_inf, c_ok, c_no = st.columns([0.6, 0.2, 0.2])

                        # 🚫 impede aprovar própria solicitação
                        if oc["email_solicitante"] == email_logado:
                            c_inf.warning("⚠️ Você não pode aprovar sua própria solicitação.")
                            continue
                        
                        # --- ONDE VOCÊ MUDA (LOGICA DE BUSCA DA UNIDADE) ---
                        unidade_func = next((u.get('unidade', 'Sem Unidade') 
                                            for u in st.session_state.db_usuarios 
                                            if u['email'] == oc['email_solicitante']), 'N/A')
    
                        # Substitua a sua linha antiga do texto_base por essa:
                        texto_base = f"**{oc['solicitante']}** ({unidade_func})\n\n📅 {oc.get('data','')}\nMotivo: {oc.get('motivo','')}"
                        
                        if oc.get('horarios'): 
                            texto_base += f"\n🕒 {oc['horarios']}"
                        
                        c_inf.write(texto_base)
                        
                        # Criamos um único expander para não poluir a tela
                        with c_inf.expander("📄 Detalhes e Documentos"):
                            # Mostra a justificativa se existir
                            if oc.get("detalhes"):
                                st.write(f"**Justificativa:** {oc['detalhes']}")
                            
                            # BUSCA O ANEXO (Tenta os dois nomes de coluna mais comuns)
                            link_arquivo = oc.get("anexo") or oc.get("anexo_url")
                            
                            if link_arquivo:
                                st.divider() # Linha para separar texto do anexo
                                st.write("**Comprovante:**")
                                
                                # Se o link terminar com imagem, ele abre direto
                                if any(ext in str(link_arquivo).lower() for ext in ['.png', '.jpg', '.jpeg']):
                                    st.image(link_arquivo, use_container_width=True)
                                else:
                                    # Se for PDF ou outro arquivo, cria um botão para abrir
                                    st.link_button("📂 Abrir Arquivo/PDF", link_arquivo)
                            else:
                                st.caption("⚠️ Nenhum anexo enviado.")

                        # --- BOTÃO APROVAR (A lógica muda conforme o cargo) ---
                        if c_ok.button("✅ Aprovar", key=f"apr_ok_{oc['id']}", use_container_width=True):
                            # Regra de Ouro: Se for folga, muda o status para o Gestor Máximo ver
                            if "Folga" in oc['motivo']:
                                novo_status = "⏳ Aguardando Direção"
                                info_msg = "Folga aprovada e enviada para o Gestor Máximo!"
                            else:
                                # Outros motivos (esquecimento, erro de relógio) o Enfermeiro já finaliza
                                novo_status = "✅ Aprovado"
                                info_msg = "Ocorrência finalizada com sucesso!"
                        
                            try:
                                # Atualiza no Supabase
                                supabase.table("ocorrencias").update({
                                    "status": novo_status,
                                    "aprovado_por": f"{user['nome']} (Enfermeiro/Supervisor)"
                                }).eq("id", oc['id']).execute()

                                registrar_log(oc['id'], f"Aprovação inicial realizada. Status alterado para: {novo_status}")

                                st.session_state.db_ocorrencias = carregar_ocorrencias()
                                st.success(info_msg)
                                st.rerun()
                                
                                st.session_state.db_ocorrencias = carregar_ocorrencias()
                                st.success(info_msg)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao processar: {e}")

                        # --- BOTÃO NEGAR ---
                        if c_no.button("❌ Negar", key=f"apr_no_{oc['id']}", use_container_width=True):
                            try:
                                supabase.table("ocorrencias").update({
                                    "status": "❌ Negado",
                                    "aprovado_por": f"{user['nome']} ({user['cargo']})"
                                }).eq("id", oc['id']).execute()

                                registrar_log(oc['id'], "Solicitação NEGADA pelo gestor da unidade.")

                                st.session_state.db_ocorrencias = carregar_ocorrencias()
                                st.warning("Ocorrência negada.")
                                st.rerun()
                                                                

                                
                                st.session_state.db_ocorrencias = carregar_ocorrencias()
                                st.warning("Ocorrência negada.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")

# ---------------- TAB NOVA OCORRÊNCIA ----------------
    with tab_nova:
            st.header("📝 Nova Solicitação")
            
            # 1. O que o usuário vê (Estético)
            opcoes_tela = ["Ajuste no ponto", "Folga"]
            escolha_usuario = st.radio("Selecione a categoria:", opcoes_tela, horizontal=True)
            
            # 2. "Tradução" para o Banco de Dados (Lógica Interna)
            mapa_categorias = {
                "Ajuste no ponto": "Ocorrência de Ponto",
                "Folga": "Folga"
            }
            categoria = mapa_categorias[escolha_usuario] 
            
            # LÓGICA DE SELEÇÃO DE MOTIVOS
            if categoria == "Ocorrência de Ponto":
                motivo_pai = st.selectbox("Tipo de Ocorrência:", ["Esquecimento", "Atestado", "Erro no Relógio", "Outros"])
                
                # O detalhe do atestado deve estar DENTRO do bloco da Ocorrência
                if motivo_pai == "Atestado":
                    detalhe_especifico = st.selectbox("Tipo de Atestado:", 
                                                     ["Médico", "Acompanhante", "Comparecimento", "Doação de Sangue"])
                else:
                    detalhe_especifico = ""
            else:
                # Este ELSE agora está alinhado com o IF da categoria (Linha 13 acima)
                motivo_pai = "Folga"
                detalhe_especifico = st.selectbox("Folga referente a:", [
                    "BANCO DE HORAS", "FOLGA ABONADA (Art. 56, XII)", "SERVIÇO ELEITORAL (TRE)",
                    "CAMPANHA DE VACINAÇÃO", "ABONO NATALÍCIO (Art. 56, X)", "OUTROS"
                ])
        
            with st.form("f_ponto_unico", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                data_inicio = col_a.date_input("Data inicial")
                data_fim = col_b.date_input("Data final")
        
                # 3. Lógica de Horários (Usa a variável 'categoria' traduzida)
                if categoria == "Ocorrência de Ponto" and motivo_pai != "Atestado":
                    st.write("---")
                    st.write("📌 **Informe os horários para ajuste:**")
                    h_cols = st.columns(4)
                    h1 = h_cols[0].time_input("Entrada", value=time(0,0))
                    h2 = h_cols[1].time_input("S. Almoço", value=time(0,0))
                    h3 = h_cols[2].time_input("R. Almoço", value=time(0,0))
                    h4 = h_cols[3].time_input("Saída", value=time(0,0))
                    txt_h = f"{h1.strftime('%H:%M')} | {h2.strftime('%H:%M')} | {h3.strftime('%H:%M')} | {h4.strftime('%H:%M')}"
                else:
                    txt_h = "Período Integral"
        
                st.write("---")
                just = st.text_area("Justificativa / Observações adicionais:")
                
                # Verificação de anexo
                anexo_obrigatorio = False
                if motivo_pai == "Atestado":
                    anexo_obrigatorio = True
                elif categoria == "Folga" and detalhe_especifico == "SERVIÇO ELEITORAL (TRE)":
                    anexo_obrigatorio = True
                
                is_obrigatorio = " (Obrigatório)" if anexo_obrigatorio else " (Opcional)"
                anexo_f = st.file_uploader(f"📤 Anexar Comprovante{is_obrigatorio}", type=["png", "jpg", "jpeg", "pdf"])
                
                enviar = st.form_submit_button("Enviar Solicitação", use_container_width=True)
        
                if enviar:
                    if data_fim < data_inicio:
                        st.error("❌ A data final não pode ser anterior à inicial.")
                        st.stop()
                    
                    if anexo_obrigatorio and not anexo_f:
                        st.error("❌ O anexo é obrigatório para este tipo de solicitação.")
                        st.stop()
        
                    motivo_final = f"{motivo_pai}: {detalhe_especifico}" if detalhe_especifico else motivo_pai
        
                    with st.spinner("Enviando para o sistema..."):
                        link_final_anexo = ""
                        if anexo_f:
                            try:
                                nome_arquivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{anexo_f.name}"
                                caminho_storage = f"comprovantes/{nome_arquivo}"
                                supabase.storage.from_("anexos").upload(
                                    path=caminho_storage, 
                                    file=anexo_f.getvalue(),
                                    file_options={"content-type": anexo_f.type}
                                )
                                link_final_anexo = supabase.storage.from_("anexos").get_public_url(caminho_storage)
                            except Exception as e:
                                st.error(f"Erro no upload: {e}")
        
                        txt_data = f"{data_inicio} até {data_fim}" if data_inicio != data_fim else str(data_inicio)
                        
                        nova_ocorrencia = {
                            "solicitante": st.session_state.usuario_logado.get('nome'),
                            "email_solicitante": st.session_state.usuario_logado["email"],
                            "unidade": st.session_state.usuario_logado.get("unidade"),
                            "data": txt_data,
                            "motivo": motivo_final,
                            "status": "⏳ Pendente",
                            "detalhes": just,
                            "horarios": txt_h,
                            "arquivado": "Não",
                            "anexo": link_final_anexo
                        }
        
                        try:
                            res_insert = supabase.table("ocorrencias").insert(nova_ocorrencia).execute()
                            if res_insert.data:
                                novo_id = res_insert.data[0]['id']
                                registrar_log(novo_id, "Solicitação criada pelo funcionário")
    
                            st.cache_data.clear() 
                            st.session_state.db_ocorrencias = carregar_ocorrencias()
                            st.success("✅ Solicitação enviada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar no banco: {e}")
    # ---------------- HISTÓRICO ----------------

    with tab_hist:
        st.subheader("📜 Meu Histórico")

        meu_h = [o for o in st.session_state.db_ocorrencias if o['email_solicitante'] == email_logado]

        if meu_h:
            for o in meu_h:
                with st.container(border=True):
                    col_txt, col_btn = st.columns([0.8, 0.2])

                    with col_txt:
                        # 1. LINHA PRINCIPAL COLORIDA (Troquei st.write por st.markdown)
                        st.markdown(f"📅 {o.get('data','')} | {o.get('motivo','')} | Status: :{cor_status(o.get('status',''))}[**{o.get('status','')}**]")

                        with st.expander("🕒 Ver Linha do Tempo / Auditoria"):
                            try:
                                res_logs = supabase.table("logs_atividades").select("*").eq("ocorrencia_id", str(o['id'])).order("created_at", desc=False).execute()
                                
                                if res_logs.data:
                                    for log in res_logs.data:
                                        # 1. FORMATAMOS A DATA ANTES DE EXIBIR
                                        data_br = formatar_data_brasilia(log['created_at'])
                                        
                                        # 2. EXIBIMOS COM O HORÁRIO CORRIGIDO
                                        st.markdown(f"🔹 **{log['acao']}**")
                                        st.caption(f"🕒 {data_br} — por {log['quem_fez']}")
                                        st.divider()
                                else:
                                    st.info("Aguardando processamento inicial.")
    
                            except Exception as e:
                                st.error(f"Erro Detalhado na consulta de logs: {e}")
                
                        # 2. EXIBIÇÃO DO APROVADOR COM DESTAQUE
                        if o.get("aprovado_por"):
                            st.info(f"✅ Analisado por: {o['aprovado_por']}")
                            
                        if o.get("horarios"):
                            st.write(f"🕒 Horários: {o['horarios']}")
                        
                        if o.get("detalhes"):
                            with st.expander("Ver justificativa"):
                                st.write(o["detalhes"])

                    # Lógica do botão de exclusão/cancelamento
                    if col_btn.button("🗑️ Cancelar", key=f"canc_user_{o['id']}"):
                        try:
                            # 1. Remove do Supabase
                            supabase.table("ocorrencias").delete().eq("id", o['id']).execute()
                            
                            # 2. LIMPA O CACHE DO STREAMLIT (Fundamental para sumir na hora!)
                            st.cache_data.clear()
                            
                            # 3. Atualiza a lista na memória e recarrega a página
                            st.session_state.db_ocorrencias = carregar_ocorrencias()
                            st.success("Solicitação cancelada.")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Erro ao cancelar: {e}")

                    # Download do anexo
                    # --- NOVO BLOCO DE ANEXOS ---
                    if o.get("anexo"):
                        # Cria duas colunas para os botões ficarem lado a lado
                        col_v, col_d = st.columns(2)
                        
                        # Botão 1: Apenas abre o link para ver
                        col_v.link_button("👁️ Visualizar", o["anexo"], use_container_width=True)

                        # Botão 2: Baixa o arquivo de verdade para o PC
                        try:
                            # Faz a requisição para pegar os dados do arquivo na web
                            conteudo_arquivo = requests.get(o["anexo"]).content
                            nome_exibicao = o["anexo"].split("/")[-1] # Pega o final da URL como nome

                            col_d.download_button(
                                label="📁 Baixar Arquivo",
                                data=conteudo_arquivo,
                                file_name=nome_exibicao,
                                mime="application/octet-stream",
                                key=f"dl_user_{o['id']}", # Identificador único para cada linha
                                use_container_width=True
                            )
                        except Exception as e:
                            col_d.error("Erro ao processar download")
        else:

            st.info("Você ainda não possui ocorrências registradas.")


    if tab_decididos:
            with tab_decididos:
                st.subheader("✅ Ocorrências Analisadas por Mim")
                
                # Filtra tudo que FOI ANALISADO pelo nome do usuário logado
                meus_decididos = [
                    o for o in st.session_state.db_ocorrencias 
                    if o.get("aprovado_por") and user['nome'] in str(o.get("aprovado_por"))
                ]
    
                if not meus_decididos:
                    st.info("Você ainda não realizou nenhuma aprovação ou negativa.")
                else:
                    for o in meus_decididos:
                        with st.container(border=True):
                            st.markdown(f"**👤 Funcionário:** {o['solicitante']}")
                            st.markdown(f"📅 {o['data']} | Motivo: {o['motivo']}")
                            
                            # Mostra o status com a cor correta
                            status_atual = o.get('status', '')
                            if "Aprovado" in status_atual:
                                st.success(f"Status: {status_atual}")
                            elif "Negado" in status_atual:
                                st.error(f"Status: {status_atual}")
                            else:
                                st.warning(f"Status: {status_atual}")
    
                            if o.get("anexo"):
                                st.link_button("👁️ Ver Comprovante", o["anexo"], use_container_width=True)
                                # Use isso apenas uma vez para criar o acesso, depois apague o bloco
if st.button("Executar Criação de Gestor Inicial"):
    criar_gestor_maximo("Nome do Diretor", "diretor_admin", "SenhaMestra123")








 































































































































































































































































