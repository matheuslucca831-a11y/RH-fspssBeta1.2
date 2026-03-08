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

def remover_funcionario_da_unidade(email_func):
    lider_email = st.session_state.usuario_logado['email']

    # Remove vínculo lider-liderado
    supabase.table("vinculos")\
        .delete()\
        .eq("lider", lider_email)\
        .eq("liderado", email_func)\
        .execute()

    # Atualiza unidade do usuário para nulo
    supabase.table("usuarios")\
        .update({"unidade": None})\
        .eq("email", email_func)\
        .execute()

    # Atualiza memória local para refletir a mudança
    for u in st.session_state.db_usuarios:
        if u['email'] == email_func:
            u['unidade'] = None

    
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
def carregar_ocorrencias():
    try:
        # .order("id", desc=True) faz com que a última cadastrada apareça primeiro
        res = supabase.table("ocorrencias").select("*").order("id", desc=True).execute()
        
        # Garante que retorne uma lista vazia se não houver dados, evitando erros de loop
        return res.data if res.data else []
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
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplZGd5dmVraXJtc3F2c3Rxdmp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2Nzg0NzgsImV4cCI6MjA4ODI1NDQ3OH0.rjJFysv6U7skPJ1UDPDysgTNpdAHSYxT0gxl_C5pDn8"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# RESTAURA LOGIN DO SUPABASE
if "supabase_session" in st.session_state:
        supabase.auth.set_session(
            st.session_state.supabase_session.access_token,
            st.session_state.supabase_session.refresh_token
        )

# FUNÇÃO PARA CARREGAR USUÁRIOS
def carregar_usuarios():
    response = supabase.table("usuarios").select("*").execute()
    return response.data


# 🔹 INICIALIZA A LISTA DE USUÁRIOS
if "db_usuarios" not in st.session_state:
    st.session_state.db_usuarios = carregar_usuarios()


print(gerar_hash("suasenha"))

# recarrega usuários
st.session_state.db_usuarios = carregar_usuarios()

    

def salvar_csv(nome_arquivo, dados):
    pd.DataFrame(dados).to_csv(nome_arquivo, index=False)




# ---------------- CONFIG ----------------
LOGIN_EXPIRY_MIN = 1

cookies = EncryptedCookieManager(
    prefix="rh_app",
    password="uma_senha_super_secreta_aqui"
)

if not cookies.ready():
    st.stop()

# Inicializa session_state
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None


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
email_temp = carregar_login()
if email_temp:
    # busca o usuário pelo email no banco
    user = next((u for u in st.session_state.db_usuarios if u["email"] == email_temp), None)
    if user:
        st.session_state.autenticado = True
        st.session_state.usuario_logado = user

# --- Tela de login ---
if not st.session_state.autenticado:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.write("# 🔐 RH Digital - FSPSS")
        with st.container(border=True):
            st.subheader("Acesso ao Sistema")
            e_in = st.text_input("Matrícula")
            s_in = st.text_input("(Senha)", type="password")
            if st.button("Entrar", use_container_width=True):
                email_login = f"{str(e_in).strip().lower()}@rh12.com"
                senha_login = s_in
            
                try:
                    # 1️⃣ Login no Supabase Auth
                    auth_resposta = supabase.auth.sign_in_with_password({
                        "email": email_login,
                        "password": senha_login
                    })
            
                    # 2️⃣ Verifica se autenticou
                    if auth_resposta.user:
            
                        # salva sessão do supabase
                        st.session_state.supabase_session = auth_resposta.session
            
                        user_id = auth_resposta.user.id
            
                        # 3️⃣ Busca usuário na tabela usuarios
                        usuario_res = supabase.table("usuarios").select("*").eq("email", email_login).execute()
            
                        if usuario_res.data:
                            usuario = usuario_res.data[0]
            
                            # salva no session_state
                            st.session_state.usuario_logado = usuario
                            st.session_state.autenticado = True
                            st.session_state.login_time = datetime.now()
            
                            salvar_login(email_login)
            
                            st.success(f"✅ Bem-vindo, {usuario['nome']}!")
                            st.rerun()
            
                        else:
                            st.error("❌ Usuário autenticado mas não encontrado na tabela usuarios.")
            
                    else:
                        st.error("❌ E-mail ou senha inválidos.")
            
                except Exception as e:
                    st.error("❌ Falha na conexão ou dados incorretos.")
                    st.write(e)
                                # st.write(e) # Use apenas para debug se precisar
# Trava de segurança: Se não autenticou, para o script aqui e não executa o resto
if not st.session_state.get("autenticado", False) or st.session_state.usuario_logado is None:
    st.stop()

# Só chega aqui se o usuário existir e estiver logado
user = st.session_state.usuario_logado
email_logado = user['email']

if st.sidebar.button("🚪 Sair", key="logout_btn"):
    # 1. Limpa o estado da memória
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None
    
    # 2. Deleta o arquivo de login temporário (ESSENCIAL)
    apagar_login() 
    
    # 3. Limpa os cookies (se estiver usando a biblioteca de cookies)
    if 'cookies' in locals():
        cookies["usuario"] = ""
        cookies["login_time"] = ""
        cookies.save()
    
    # 4. Reinicia o app limpo
    st.rerun()

st.title(f"Olá, {user['nome']}!")


# --------------------------------------------------
# 5. PAINEL GESTOR MÁXIMO (ADMIN COMPLETO)
# --------------------------------------------------
if user['cargo'] == "Gestor Máximo":
    st.header("Painel Administrativo Central")
    t_users, t_vinc, t_aprovar, t_hist, t_arq = st.tabs([
        "👥 Equipe", 
        "🔗 Vínculos", 
        "✅ Aprovar Folgas", # Nova aba dedicada
        "📊 Monitoramento", 
        "📦 Arquivo Morto"
    ])
    with t_users:
        with st.expander("➕ Novo Usuário"):
            with st.form("cad_u", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n_n = c1.text_input("Nome")
                n_m = c2.text_input("Senha")
                n_e = c1.text_input("Matrícula")
                n_c = c2.selectbox("Cargo", ["Funcionário", "Enfermeiro", "Supervisor", "Gestor Máximo"])
                if st.form_submit_button("Salvar"):
                                # --- VALIDAÇÃO DE SEGURANÇA ---
                                if len(str(n_m).strip()) < 6:
                                    st.error("🔒 A senha deve ter no mínimo 6 caracteres.")
                                elif not n_e or not n_n:
                                    st.warning("⚠️ Preencha Nome e Matrícula.")
                                else:
                                    email_interno = f"{n_e}@rh12.com"

                                    novo_usuario = {
                                        "email": email_interno,  # email técnico
                                        "nome": n_n,
                                        "cargo": n_c,
                                        "matricula": gerar_hash(str(n_m)) # Senha (Hash)
                                    }
                                
                                    try:
                                        # cria usuário no sistema de autenticação
                                        supabase.auth.sign_up({
                                            "email": email_interno,
                                            "password": n_m
                                        })
                                        # salva na tabela usuarios

                                        supabase.table("usuarios").insert(novo_usuario).execute()
                                        # --- LINHA CRÍTICA: Atualiza a lista na memória do app ---
                                        st.session_state.db_usuarios = carregar_usuarios() 
                                        st.success(f"Usuário {n_n} cadastrado!")
                                        st.rerun()
                                
                                    except Exception as e:
                                        st.error("Erro ao salvar usuário no Supabase")
                                        st.write(e)

        busca = st.text_input("🔍 Pesquisar:")
        for u in [u for u in st.session_state.db_usuarios if busca.lower() in u['nome'].lower() or busca in str(u.get('matricula', ''))]:
            if u['email'] == email_logado: continue
            with st.expander(f"👤 {u['nome']} ({u['cargo']})"):
                pode_editar = st.session_state.usuario_logado["cargo"] == "Gestor Máximo"

                col1, col2 = st.columns(2)

                novo_nome = col1.text_input(
                    "Nome",
                    value=u["nome"],
                    key=f"n_{u['email']}",
                    disabled=not pode_editar
                )

                nova_matricula_login = col2.text_input(
                    "Matrícula (Login)",
                    value=u["email"].split("@")[0],
                    key=f"e_{u['email']}",
                    disabled=not pode_editar
                )

                nova_senha = col1.text_input(
                    "Nova Senha (deixe em branco para não alterar)",
                    type="password",
                    key=f"s_{u['email']}",
                    disabled=not pode_editar
                )

                novo_cargo = col2.selectbox(
                    "Cargo",
                    ["Funcionário", "Enfermeiro", "Supervisor", "Gestor Máximo"],
                    index=["Funcionário", "Enfermeiro", "Supervisor", "Gestor Máximo"].index(u['cargo']),
                    key=f"c_{u['email']}",
                    disabled=not pode_editar
                )

                c1, c2 = st.columns(2)

                if c1.button("💾 Atualizar", key=f"up_{u['email']}") and pode_editar:
                
                    email_antigo = u["email"]
                
                    if nova_senha:
                        senha_hash = gerar_hash(nova_senha)
                    else:
                        senha_hash = u["matricula"]
                
                    try:
                        supabase.table("usuarios").update({
                            "nome": novo_nome,
                            "email": nova_matricula_login,
                            "cargo": novo_cargo,
                            "matricula": senha_hash
                        }).eq("email", email_antigo).execute()
                
                        st.session_state.db_usuarios = carregar_usuarios()
                
                        st.success("Usuário atualizado!")
                        st.rerun()
                
                    except Exception as e:
                        st.error("Erro ao atualizar usuário")
                        st.write(e)
                    
                    except Exception as e:
                        st.error("Erro ao atualizar usuário")

                if c2.button("🗑️ Excluir", key=f"del_{u['email']}") and pode_editar:
                    try:
                        supabase.table("usuarios").delete().eq("email", u["email"]).execute()
                        st.success("Usuário excluído!")
                        st.rerun()
                    
                    except Exception as e:
                        st.error("Erro ao excluir usuário")



    with t_vinc:
        st.subheader("🏢 Gestão de Unidades e Equipes")
    
        # --- PARTE 1: Criar nova unidade ---
        with st.expander("➕ Criar Nova Unidade/Setor", expanded=False):
            with st.form("form_unidade"):
                nova_unidade = st.text_input("Nome da Unidade (ex: USF Boiçucanga, Administrativo):")
                if st.form_submit_button("Cadastrar Unidade"):
                    if nova_unidade:
                        try:
                            supabase.table("unidades").insert({"nome": nova_unidade}).execute()
                            st.success("✅ Unidade criada!")
                            st.session_state.rerun_needed = True
                        except Exception as e:
                            st.error(f"❌ Erro ao criar: {e}")
                    else:
                        st.warning("⚠️ Digite um nome para a unidade.")
    
        # --- PARTE 2: Carrega unidades ---
        res_unidades = supabase.table("unidades").select("*").execute()
        unidades_db = res_unidades.data if res_unidades.data else []
    
        if unidades_db:
            st.markdown("---")
            st.markdown("### 🔗 Alocar Funcionários em Unidade")
    
            # Campo de pesquisa + seleção em um só selectbox
            pesquisa_unidade = st.text_input("Pesquise ou selecione a Unidade:", key="pesquisa_unidade_aloc")
            unidades_filtradas = [u for u in unidades_db if pesquisa_unidade.lower() in u['nome'].lower()]
            nomes_filtrados = [u['nome'] for u in unidades_filtradas]
            unidade_nome_sel = st.selectbox("Unidade destino:", [""] + nomes_filtrados)
    
            unidade_selecionada = next((u for u in unidades_db if u['nome'] == unidade_nome_sel), None)
    
            if unidade_selecionada:
                st.markdown(f"#### 👥 Equipe para: {unidade_selecionada['nome']}")
                todos_users = [u['email'] for u in st.session_state.db_usuarios]
    
                u_func = st.multiselect(
                    "Selecionar Funcionários para alocar:",
                    todos_users,
                    format_func=lambda x: next(u['nome'] for u in st.session_state.db_usuarios if u['email'] == x)
                )
    
                if st.button("🚀 Confirmar Alocação", use_container_width=True):
                    if not u_func:
                        st.warning("⚠️ Selecione pelo menos um funcionário.")
                    else:
                        try:
                            lider_email = st.session_state.usuario_logado['email']
                            for email in u_func:
                                # Registra vínculo
                                supabase.table("vinculos").insert({
                                    "lider": lider_email,
                                    "liderado": email
                                }).execute()
    
                                # Atualiza unidade no usuário
                                supabase.table("usuarios").update({
                                    "unidade": unidade_selecionada['nome']
                                }).eq("email", email).execute()
    
                            # Atualiza cache local
                            for u in st.session_state.db_usuarios:
                                if u['email'] in u_func:
                                    u['unidade'] = unidade_selecionada['nome']
    
                            st.success(f"✅ Funcionários alocados com sucesso em {unidade_selecionada['nome']}!")
                            st.session_state.rerun_needed = True
                        except Exception as e:
                            st.error(f"❌ Erro ao salvar: {e}")
    
        # --- PARTE 3: Aba de pesquisa de unidades e remoção de funcionários ---
        st.markdown("---")
        st.subheader("🔎 Pesquisar Unidades")
    
        pesquisa_unidade = st.text_input("Digite o nome da unidade para pesquisa", key="pesquisa_unidade")
        unidades_filtradas_pesquisa = [u for u in unidades_db if pesquisa_unidade.lower() in u['nome'].lower()]
    
        if "funcionario_para_remover" not in st.session_state:
            st.session_state.funcionario_para_remover = None
            st.session_state.unidade_para_remover = None
    
        if unidades_filtradas_pesquisa:
            for uni in unidades_filtradas_pesquisa:
                with st.container(border=True):
                    st.markdown(f"### 📍 {uni['nome']}")
                    membros = [u for u in st.session_state.db_usuarios if u.get('unidade') == uni['nome']]
    
                    if membros:
                        for m in membros:
                            cargo_emoji = "🩺" if m['cargo'] == "Enfermeiro" else "👤"
                            col1, col2 = st.columns([0.9, 0.1])
                            with col1:
                                st.write(f"{cargo_emoji} **{m['nome']}** ({m['cargo']})")
                            with col2:
                                if st.button("❌", key=f"remover_{uni['id']}_{m['email']}"):
                                    st.session_state.funcionario_para_remover = m['email']
                                    st.session_state.unidade_para_remover = uni['nome']
                    else:
                        st.caption("Nenhum funcionário nesta unidade.")
        else:
            st.info("Nenhuma unidade encontrada.")
    
    # --- Executa remoção de funcionário fora do loop ---
    if st.session_state.funcionario_para_remover:
        remover_funcionario_da_unidade(st.session_state.funcionario_para_remover)
        st.success(f"{st.session_state.funcionario_para_remover} removido da unidade {st.session_state.unidade_para_remover}.")
        st.session_state.funcionario_para_remover = None
        st.session_state.unidade_para_remover = None
        st.session_state.rerun_needed = True
    
    # --- Chama rerun seguro uma vez ---
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
                        if st.button("✅ DEFERIR", key=f"def_{f['id']}", use_container_width=True):
                            supabase.table("ocorrencias").update({
                                "status": "✅ Deferido",
                                "aprovado_por": f"{f.get('aprovado_por')} / Direção"
                            }).eq("id", f['id']).execute()
                            st.session_state.db_ocorrencias = carregar_ocorrencias()
                            st.rerun()
                            
                        if st.button("❌ INDEFERIR", key=f"ind_{f['id']}", use_container_width=True):
                            # Opcional: Adicionar um campo de observação da Direção antes de negar
                            supabase.table("ocorrencias").update({
                                "status": "❌ Indeferido",
                                "aprovado_por": "Direção"
                            }).eq("id", f['id']).execute()
                            st.session_state.db_ocorrencias = carregar_ocorrencias()
                            st.rerun()




    
    with t_hist:
                st.subheader("📊 Monitoramento Geral")
                
                # --- 1. INICIALIZAÇÃO (Evita o NameError) ---
                f_nome = ""
                f_status = "Todos"
                f_motivo = "Todos"
                f_data_sel = None
    
                if st.session_state.db_ocorrencias:
                    df_oc = pd.DataFrame(st.session_state.db_ocorrencias)
                    
                    # --- 2. INTERFACE DE FILTROS ---
                    with st.container(border=True):
                        f1, f2, f3, f4, f5 = st.columns(5)
                        
                        with f1:
                            f_nome = st.text_input("👤 Nome", placeholder="Buscar...")
                        with f2:
                            opcoes_status = ["Todos"] + sorted(list(df_oc["status"].unique()))
                            f_status = st.selectbox("📌 Status", opcoes_status)
                        with f3:
                            opcoes_motivo = [
                                "Todos", 
                                "🎯 Todas as Folgas", 
                                "⏰ Todas as Ocorrências"
                            ] + sorted(list(df_oc["motivo"].unique()))
                            f_motivo = st.selectbox("💡 Motivo", opcoes_motivo)
                        with f4:
                            f_data_sel = st.date_input("📅 Data", value=None, format="DD/MM/YYYY")
                        with f5:
                            ordem = st.selectbox("⏳ Ordem", ["Mais Recentes", "Mais Antigas"])
    
                    # --- 3. LÓGICA DE FILTRAGEM (Ajustada para os novos grupos) ---
                    mask = df_oc["arquivado"] != "Sim"
    
                    if f_nome:
                        mask &= df_oc["solicitante"].str.contains(f_nome, case=False, na=False)
    
                    if f_status != "Todos":
                        mask &= df_oc["status"] == f_status
    
                    # Lógica para os botões agrupados
                    if f_motivo == "🎯 Todas as Folgas":
                        mask &= df_oc["motivo"].str.contains("Folga", case=False, na=False)
                    elif f_motivo == "⏰ Todas as Ocorrências":
                        # Pega tudo que NÃO tem "Folga" no nome
                        mask &= ~df_oc["motivo"].str.contains("Folga", case=False, na=False)
                    elif f_motivo != "Todos":
                        mask &= df_oc["motivo"] == f_motivo
    
                    if f_data_sel:
                        data_str = f_data_sel.strftime("%Y-%m-%d")
                        mask &= df_oc["data"].astype(str).str.contains(data_str, na=False)
    
                    df_filtrado = df_oc[mask]

                    ordem_crescente = (ordem == "Mais Antigas")
                    df_filtrado = df_filtrado.sort_values(by="id", ascending=ordem_crescente)
    
                    # --- 4. EXIBIÇÃO DOS CARDS ---
                    if df_filtrado.empty:
                        st.info("Nenhum registro encontrado para os filtros selecionados.")
                    else:
                        # Mostra a quantidade encontrada (Dica de ADS para o gestor)
                        st.caption(f"🔢 {len(df_filtrado)} registros encontrados")
                        
                        for _, o in df_filtrado.iterrows():
                            with st.container(border=True):
                                c1, c2 = st.columns([0.8, 0.2])
                                
                                resumo = (
                                    f"👤 **{o['solicitante']}**\n\n"
                                    f"📅 {o['data']} | 💡 Motivo: {o['motivo']}\n"
                                    f"📌 Status: :{cor_status(o['status'])}[**{o['status']}**]"
                                )
    
                                if "aprovado_por" in o and pd.notna(o["aprovado_por"]) and o["aprovado_por"] != "":
                                    resumo += f"\n\n✅ **Analisado por:** {o['aprovado_por']}"
    
                                if o.get("horarios"):
                                    resumo += f"\n🕒 {o['horarios']}"
    
                                c1.markdown(resumo)
    
                                if o.get("detalhes"):
                                    with c1.expander("Ver justificativa"):
                                        st.write(o["detalhes"])
    
                                if o.get("anexo"):
                                    with st.expander("🖼️ Visualizar Documento", expanded=False):
                                        exibir_anexo(o["anexo"])
    
                                # Botões de Ação
                                if c2.button("📦 Arquivar", key=f"arq_filt_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("ocorrencias").update({"arquivado": "Sim"}).eq("id", o['id']).execute()
                                        st.session_state.db_ocorrencias = carregar_ocorrencias()
                                        st.success("Arquivado!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")
    
                                if c2.button("🗑️ Excluir", key=f"exc_adm_{o['id']}", use_container_width=True):
                                    try:
                                        supabase.table("ocorrencias").delete().eq("id", o['id']).execute()
                                        st.session_state.db_ocorrencias = carregar_ocorrencias()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")
                else:
                    st.info("Sem registros no banco de dados.")


    with t_arq:
        st.subheader("📦 Arquivo Morto - Ocorrências Arquivadas")
    
        if st.session_state.db_ocorrencias:
            # Cria o DataFrame
            df_completo = pd.DataFrame(st.session_state.db_ocorrencias)
            
            # Garante que a coluna existe e trata valores nulos/vazios
            if "arquivado" not in df_completo.columns:
                df_completo["arquivado"] = "Não"
            else:
                df_completo["arquivado"] = df_completo["arquivado"].fillna("Não").replace("", "Não")
    
            # FILTRO: Pega apenas o que é "Sim"
            df_arq = df_completo[df_completo["arquivado"] == "Sim"]
    
            if not df_arq.empty:
                # ... (seu código de filtros f1, f2, f3, f4 aqui) ...
                
                # Lógica de máscara para os filtros internos do arquivo morto
                mask_arq = pd.Series([True] * len(df_arq), index=df_arq.index)
                
                if f_nome:
                    mask_arq &= df_arq["solicitante"].str.contains(f_nome, case=False, na=False)
                # ... (aplique os outros filtros f_status, f_motivo, f_data na mask_arq) ...
                
                df_arq_filtrado = df_arq[mask_arq]
                
                # Exibição dos cards (similar ao monitoramento geral)
                for _, o in df_arq_filtrado.iterrows():
                    with st.container(border=True):
                        st.write(f"👤 **{o['solicitante']}**")
                        st.write(f"📅 {o['data']} | Status: {o['status']}")
                        
                        # Botão para DESARQUIVAR (Opcional, mas útil)
                        if st.button("📤 Restaurar", key=f"rest_{o['id']}"):
                            supabase.table("ocorrencias").update({"arquivado": "Não"}).eq("id", o['id']).execute()
                            st.session_state.db_ocorrencias = carregar_ocorrencias()
                            st.rerun()
            else:
                st.info("Nenhum registro no arquivo morto.")
        else:
            st.info("Sem registros no banco de dados.")

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
        # 1. Descobrimos quem são os funcionários que pertencem à mesma unidade que o líder
        equipe_unidade = [
            u['email'] for u in st.session_state.db_usuarios 
            if u.get('unidade') == minha_unidade
        ]
        
        # 2. Filtramos as ocorrências: Devem ser "Pendentes" E o solicitante deve ser da unidade
        pendentes = [
            o for o in st.session_state.db_ocorrencias 
            if o["status"] == "⏳ Pendente" and o["email_solicitante"] in equipe_unidade
        ]
        
        tab_aprov, tab_nova, tab_hist, tab_decididos = st.tabs([
            f"📋 Aprovações ({len(pendentes)})", "📝 Nova ocorrência", "📜 Meu Histórico", "✅ Minhas Decisões"
        ])
        
    elif user['cargo'] == "Gestor Máximo":
        # O Gestor Máximo continua vendo TUDO que está com a direção, independente da unidade
        pendentes = [o for o in st.session_state.db_ocorrencias if o["status"] == "⏳ Aguardando Direção"]
        
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
                                st.session_state.db_ocorrencias = carregar_ocorrencias()
                                st.warning("Ocorrência negada.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")

# ---------------- TAB NOVA OCORRÊNCIA ----------------
    with tab_nova:
        st.header("📝 Nova Solicitação")
        
        # 1. Escolha da Categoria
        categoria = st.radio("Selecione a categoria:", ["Ocorrência de Ponto", "Folga"], horizontal=True)
        
        # 2. Definição do Motivo e Detalhes
        detalhe_especifico = ""
        if categoria == "Ocorrência de Ponto":
            motivo_pai = st.selectbox("Tipo de Ocorrência:", 
                                     ["Esquecimento", "Atestado", "Erro no Relógio", "Outros"])
            if motivo_pai == "Atestado":
                detalhe_especifico = st.selectbox("Tipo de Atestado:", 
                                                 ["Médico", "Acompanhante", "Comparecimento", "Doação de Sangue"])
        else:
            motivo_pai = "Folga"
            detalhe_especifico = st.selectbox("Folga referente a:", [
                "BANCO DE HORAS", "FOLGA ABONADA (Art. 56, XII)", "SERVIÇO ELEITORAL (TRE)",
                "CAMPANHA DE VACINAÇÃO", "ABONO NATALÍCIO (Art. 56, X)", "OUTROS"
            ])
    
        with st.form("f_ponto_unico", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            data_inicio = col_a.date_input("Data inicial")
            data_fim = col_b.date_input("Data final")
    
            # 3. Lógica de Horários
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
            
            # OBRIGATORIEDADE DE ANEXO
            anexo_obrigatorio = False
            
            if motivo_pai == "Atestado":
                anexo_obrigatorio = True
            elif categoria == "Folga" and detalhe_especifico == "SERVIÇO ELEITORAL (TRE)":
                anexo_obrigatorio = True
            
            is_obrigatorio = " (Obrigatório)" if anexo_obrigatorio else " (Opcional)"
            
            anexo_f = st.file_uploader(
                f"📤 Anexar Comprovante{is_obrigatorio}",
                type=["png", "jpg", "jpeg", "pdf"]
            )
            # BOTÃO DO FORMULÁRIO
            enviar = st.form_submit_button("🚀 Enviar Solicitação", use_container_width=True)
    
            # --- PROCESSAMENTO DO ENVIO (Apenas uma vez) ---
            if enviar:
                # 1. Validação de data
                if data_fim < data_inicio:
                    st.error("❌ A data final não pode ser anterior à inicial.")
                    st.stop()
                
                # 2. Validação de anexo obrigatório
                if anexo_obrigatorio and not anexo_f:
                    st.error("❌ O anexo é obrigatório para este tipo de solicitação.")
                    st.stop()
    
                # 3. Montagem do motivo final
                motivo_final = f"{motivo_pai}: {detalhe_especifico}" if detalhe_especifico else motivo_pai
    
                with st.spinner("Enviando para o sistema..."):
                    # --- LÓGICA DE UPLOAD ---
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
    
                    # --- MONTAGEM E INSERT ---
                    txt_data = f"{data_inicio} até {data_fim}" if data_inicio != data_fim else str(data_inicio)
                    
                    nova_ocorrencia = {
                        "solicitante": st.session_state.usuario_logado.get('nome'),
                        "email_solicitante": st.session_state.usuario_logado["email"],
                        "data": txt_data,
                        "motivo": motivo_final,
                        "status": "⏳ Pendente",
                        "detalhes": just,
                        "horarios": txt_h,
                        "arquivado": "Não",
                        "anexo": link_final_anexo
                    }
    
                    try:
                        supabase.table("ocorrencias").insert(nova_ocorrencia).execute()
                        st.success("✅ Solicitação enviada com sucesso!")
                        st.session_state.db_ocorrencias = carregar_ocorrencias()
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
                            supabase.table("ocorrencias").delete().eq("id", o['id']).execute()
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






































































































































































