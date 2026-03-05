import streamlit as st
import pandas as pd
import os
import uuid
import base64
from datetime import datetime, time
import streamlit as st
from datetime import datetime, timedelta
from streamlit_cookies_manager import EncryptedCookieManager
import streamlit as st
from supabase import create_client
from passlib.hash import pbkdf2_sha256

def gerar_hash(senha):
    return pbkdf2_sha256.hash(senha)
    
def carregar_vinculos():
    try:
        res = supabase.table("vinculos").select("*").execute()
        vinc_dict = {}
        for r in res.data:
            l = r['lider']
            ld = r['liderado']
            if l not in vinc_dict:
                vinc_dict[l] = []
            vinc_dict[l].append(ld)
        return vinc_dict
    except:
        return {}

def carregar_ocorrencias():
    try:
        # Busca todas as linhas da tabela 'ocorrencias'
        res = supabase.table("ocorrencias").select("*").execute()
        return res.data
    except Exception as e:
        st.error(f"Erro ao carregar ocorrências: {e}")
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


# FUNÇÃO PARA CARREGAR USUÁRIOS
def carregar_usuarios():
    response = supabase.table("usuarios").select("*").execute()
    return response.data


# 🔹 INICIALIZA A LISTA DE USUÁRIOS
if "db_usuarios" not in st.session_state:
    st.session_state.db_usuarios = carregar_usuarios()


# verifica se o usuário 0001 já existe no banco
usuario_existe = supabase.table("usuarios").select("*").eq("email", "0001").execute()

if len(usuario_existe.data) == 0:
    usuario_padrao = {
        "email": "0001",
        "nome": "Gestor Master",
        "cargo": "Gestor Máximo",
        "matricula": gerar_hash("admin123")
    }

    supabase.table("usuarios").insert(usuario_padrao).execute()

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
def exibir_anexo(caminho_arquivo):
    if not caminho_arquivo or not os.path.exists(caminho_arquivo):
        st.warning("Arquivo físico não encontrado no servidor.")
        return

    extensao = caminho_arquivo.lower().split('.')[-1]
    
    # Se for Imagem (JPG, PNG)
    if extensao in ['jpg', 'jpeg', 'png']:
        # O use_container_width=True faz a imagem usar toda a largura do card
        st.image(caminho_arquivo, use_container_width=True)
    
    # Se for PDF
    elif extensao == 'pdf':
        with open(caminho_arquivo, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        # PDF embutido com altura generosa para leitura
        pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700" type="application/pdf">'
        st.markdown(pdf_display, unsafe_allow_html=True)
    
    else:
        st.info("Visualização direta não suportada para este formato. Use o botão de download.")

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
    df_v = pd.DataFrame(st.session_state.db_vinculos)
    if not df_v.empty and 'lider' in df_v.columns:
        st.session_state.vinculos = df_v.groupby('lider')['liderado'].apply(list).to_dict()
    else:
        st.session_state.vinculos = {}

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
                            # Garante que temos a lista mais recente antes de procurar
                            st.session_state.db_usuarios = carregar_usuarios() 
                            
                            # Busca higienizada (sem espaços e tudo em string)
                            matricula_digitada = str(e_in).strip()
                            
                            u_f = next(
                                (u for u in st.session_state.db_usuarios 
                                if str(u.get('email', '')).strip() == matricula_digitada),
                                None
                            )
            
                            if u_f and verificar_senha(s_in, u_f['matricula']):
                                st.session_state.autenticado = True
                                st.session_state.usuario_logado = u_f
                                
                                # --- MUDANÇA AQUI: Carrega os dados do Supabase para a memória ---
                                with st.spinner("Carregando dados..."):
                                    st.session_state.db_ocorrencias = carregar_ocorrencias()
                                
                                # Salva sessão temporária no arquivo/cookie
                                salvar_login(u_f["email"])
                                
                                st.success("Login realizado!")
                                st.rerun()
                            else:
                                st.error("Matrícula ou senha incorretos.")

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
    t_users, t_vinc, t_hist, t_arq = st.tabs(["👥 Equipe", "🔗 Vínculos", "📊 Monitoramento", "📦 Arquivo Morto"])

    with t_users:
        with st.expander("➕ Novo Usuário"):
            with st.form("cad_u", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n_n = c1.text_input("Nome")
                n_m = c2.text_input("Senha")
                n_e = c1.text_input("Matrícula")
                n_c = c2.selectbox("Cargo", ["Funcionário", "Enfermeiro", "Supervisor", "Gestor Máximo"])
                if st.form_submit_button("Salvar"):
                                    novo_usuario = {
                                        "email": str(n_e).strip(), # Matrícula (Login)
                                        "nome": n_n,
                                        "cargo": n_c,
                                        "matricula": gerar_hash(str(n_m)) # Senha (Hash)
                                    }
                                
                                    try:
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
                    value=u["email"],
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
                    u["nome"] = novo_nome
                    u["email"] = nova_matricula_login
                    u["cargo"] = novo_cargo

                    if nova_senha:
                        u["matricula"] = gerar_hash(nova_senha)

                    try:
                        supabase.table("usuarios").update({
                            "nome": novo_nome,
                            "email": nova_matricula_login,
                            "cargo": novo_cargo,
                            "matricula": u["matricula"]
                        }).eq("email", u["email"]).execute()
                    
                        st.success("Usuário atualizado!")
                        st.rerun()
                    
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
            st.subheader("🔗 Gerenciar Estrutura de Equipes")
            
            # Lista de quem pode ser líder
            lids = [u for u in st.session_state.db_usuarios if u['cargo'] in ['Enfermeiro', 'Supervisor']]
            
            if not lids:
                st.warning("Nenhum Enfermeiro ou Supervisor cadastrado para ser líder.")
            else:
                # --- PARTE 1: FORMULÁRIO RÁPIDO ---
                with st.expander("➕ Vincular novo Liderado a um Líder", expanded=False):
                    with st.form("form_vinc"):
                        c1, c2 = st.columns(2)
                        l_sel = c1.selectbox("Selecione o Líder:", lids, format_func=lambda x: f"{x['nome']} ({x['cargo']})")
                        
                        disp = [u['email'] for u in st.session_state.db_usuarios if u['email'] != l_sel['email']]
                        ld_sel = c2.multiselect("Selecione os Liderados:", disp, 
                                                format_func=lambda x: next(u['nome'] for u in st.session_state.db_usuarios if u['email'] == x))
                        
                        if st.form_submit_button("Confirmar Vínculo"):
                            try:
                                # 1. Remove vínculos antigos do líder para não duplicar
                                supabase.table("vinculos").delete().eq("lider", l_sel['email']).execute()
                                
                                # 2. Prepara e insere os novos registros
                                novos_regs = [{"lider": l_sel['email'], "liderado": ld} for ld in ld_sel]
                                if novos_regs:
                                    supabase.table("vinculos").insert(novos_regs).execute()
                                
                                # 3. Atualiza a memória e recarrega
                                st.session_state.vinculos = carregar_vinculos()
                                st.success("Equipe atualizada no Supabase!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar no banco: {e}")




                
                st.write("---")
                
                # --- PARTE 2: FILTRO POR NOME ---
                st.markdown("### 📋 Configuração Atual")
                
                # Campo de busca simplificado
                f_nome = st.text_input("🔍 Filtrar líder por nome", placeholder="Digite e o sistema filtrará...", key="filtro_nome")
                # Aplica o filtro na lista de líderes antes de rodar o loop
                if f_nome:
                    lids_filtrados = [l for l in lids if f_nome.lower() in l['nome'].lower()]
                else:
                    lids_filtrados = lids

                if not lids_filtrados:
                    st.info("Nenhum líder encontrado com esse nome.")
                else:
                    # --- PARTE 3: LOOP DE EXIBIÇÃO ---
                    for lider in lids_filtrados:
                        l_email = lider['email']
                        l_nome = lider['nome']
                        l_cargo = lider['cargo']
                        
                        liderados_atuais = st.session_state.vinculos.get(l_email, [])
                        qtd = len(liderados_atuais)
                        
                        with st.container(border=True):
                            col_info, col_btn = st.columns([0.8, 0.2])
                            
                            with col_info:
                                st.markdown(f"**{l_nome}** ({l_cargo})")
                                if qtd > 0:
                                    nomes_liderados = []
                                    for e in liderados_atuais:
                                        nome = next((u['nome'] for u in st.session_state.db_usuarios if u['email'] == e), e)
                                        nomes_liderados.append(f"`{nome}`")
                                    st.markdown(f"👥 {', '.join(nomes_liderados)}")
                                else:
                                    st.caption("⚠️ Ninguém vinculado a este líder.")

                            if col_btn.button("✏️ Editar", key=f"ed_vinc_{l_email}"):
                                st.session_state[f"editando_{l_email}"] = True

                            if st.session_state.get(f"editando_{l_email}"):
                                st.write(f"**Editando equipe de {l_nome}:**")
                                novo_time = st.multiselect(
                                    "Selecione os liderados:", 
                                    [u['email'] for u in st.session_state.db_usuarios if u['email'] != l_email],
                                    default=liderados_atuais,
                                    format_func=lambda x: next((u['nome'] for u in st.session_state.db_usuarios if u['email'] == x), x),
                                    key=f"ms_{l_email}"
                                )
                            
                                ce1, ce2 = st.columns(2)
                                if ce1.button("✅ Salvar", key=f"sv_{l_email}", use_container_width=True):
                                    try:
                                        # 1. Limpa os vínculos antigos desse líder no Supabase
                                        supabase.table("vinculos").delete().eq("lider", l_email).execute()
                                        
                                        # 2. Insere os novos se houver algum selecionado
                                        if novo_time:
                                            novos_vincs = [{"lider": l_email, "liderado": ld} for ld in novo_time]
                                            supabase.table("vinculos").insert(novos_vincs).execute()
                                        
                                        # 3. Atualiza a memória local (Sincroniza com o Banco)
                                        st.session_state.vinculos = carregar_vinculos()
                                        
                                        # 4. Fecha o modo de edição e reinicia
                                        if f"editando_{l_email}" in st.session_state:
                                            del st.session_state[f"editando_{l_email}"]
                                        
                                        st.success("Vínculos atualizados com sucesso!")
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"Erro ao salvar no Supabase: {e}")
    
                                if ce2.button("❌ Cancelar", key=f"cn_{l_email}", use_container_width=True):
                                    if f"editando_{l_email}" in st.session_state:
                                        del st.session_state[f"editando_{l_email}"]
                                    st.rerun()

    with t_hist:
        st.subheader("📊 Monitoramento Geral")

        # 1. CONVERSÃO PARA DATAFRAME (Para que os filtros funcionem)
        if st.session_state.db_ocorrencias:
            df_oc = pd.DataFrame(st.session_state.db_ocorrencias)
            
            # 2. ÁREA DE FILTROS (CALENDÁRIO + SELECTS)
            with st.container(border=True):
                f1, f2, f3, f4 = st.columns(4)
                
                with f1:
                    f_nome = st.text_input("👤 Nome", placeholder="Buscar...")
                with f2:
                    opcoes_status = ["Todos"] + sorted(list(df_oc["status"].unique()))
                    f_status = st.selectbox("📌 Status", opcoes_status)
                with f3:
                    opcoes_motivo = ["Todos"] + sorted(list(df_oc["motivo"].unique()))
                    f_motivo = st.selectbox("💡 Motivo", opcoes_motivo)
                with f4:
                    # Calendário para o filtro de data
                    f_data_sel = st.date_input("📅 Data", value=None, format="DD/MM/YYYY")

            # 3. LÓGICA DE FILTRAGEM (Máscara)
            mask = df_oc["arquivado"] != "Sim"
            
            if f_nome:
                mask &= df_oc["solicitante"].str.contains(f_nome, case=False, na=False)
            if f_status != "Todos":
                mask &= df_oc["status"] == f_status
            if f_motivo != "Todos":
                mask &= df_oc["motivo"] == f_motivo
            if f_data_sel:
                # Transforma a data do calendário para o texto do CSV (AAAA-MM-DD)
                data_str = f_data_sel.strftime("%Y-%m-%d")
                mask &= df_oc["data"].str.contains(data_str, na=False)

            df_filtrado = df_oc[mask]

            df_filtrado = df_oc[mask]

                # 4. EXIBIÇÃO DOS CARDS FILTRADOS (Substitua daqui para baixo)
            if df_filtrado.empty:
                    st.info("Nenhum registro encontrado.")
            else:
                    for _, o in df_filtrado.iterrows():
                        with st.container(border=True):
                            c1, c2 = st.columns([0.8, 0.2])
                            
                            # Montagem do texto principal
                            # Usamos a nossa função cor_status para colorir o status
                            resumo = (
                                f"👤 **{o['solicitante']}**\n\n"
                                f"📅 {o['data']} | 💡 Motivo: {o['motivo']}\n"
                                f"📌 Status: :{cor_status(o['status'])}[**{o['status']}**]"
                            )
                            
                            # --- ADICIONA O APROVADOR AQUI ---
                            if "aprovado_por" in o and pd.notna(o["aprovado_por"]) and o["aprovado_por"] != "":
                                resumo += f"\n\n✅ **Analisado por:** {o['aprovado_por']}"
                            
                            if o.get("horarios"):
                                resumo += f"\n🕒 {o['horarios']}"
                            
                            c1.markdown(resumo)

                            # Justificativa
                            if o.get("detalhes"):
                                with c1.expander("Ver justificativa"):
                                    st.write(o["detalhes"])

                            # --- DENTRO DO SEU LOOP DE OCORRÊNCIAS ---
                            if o.get("anexo"):
                                st.divider() # Uma linha divisória
                                
                                # Em vez de colunas pequenas, usamos um expander que ocupa a largura toda
                                with st.expander("🖼️ Visualizar Documento (Atestado/Comprovante)", expanded=False):
                                    exibir_anexo(o["anexo"])
                                
                                # Deixamos apenas o botão de baixar em uma coluna menor se desejar
                                try:
                                    with open(o["anexo"], "rb") as f:
                                        st.download_button(
                                            label="📁 Baixar Arquivo Original",
                                            data=f,
                                            file_name=os.path.basename(o["anexo"]),
                                            key=f"dl_full_{o['id']}",
                                            use_container_width=True
                                        )
                                except:
                                    st.error("Erro ao carregar arquivo para download.")
                            # Botões de Ação (Arquivar e Excluir)
                            if c2.button("📦 Arquivar", key=f"arq_filt_{o['id']}", use_container_width=True):
                                try:
                                    # Atualiza a coluna 'arquivado' para 'Sim' no registro com esse ID
                                    supabase.table("ocorrencias").update({"arquivado": "Sim"}).eq("id", o['id']).execute()
                                    st.session_state.db_ocorrencias = carregar_ocorrencias()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao arquivar: {e}")

                            if c2.button("🗑️ Excluir", key=f"exc_adm_{o['id']}", use_container_width=True):
                                try:
                                    # Remove fisicamente do banco de dados
                                    supabase.table("ocorrencias").delete().eq("id", o['id']).execute()
                                    st.session_state.db_ocorrencias = carregar_ocorrencias()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir: {e}")
        else:
            st.info("Sem registros no banco de dados.")

    with t_arq:
        st.subheader("📦 Arquivo Morto - Ocorrências Arquivadas")

        # --- GARANTIR QUE TODOS OS REGISTROS TENHAM 'arquivado' ---
        for item in st.session_state.db_ocorrencias:
            if "arquivado" not in item or item["arquivado"] == "":
                item["arquivado"] = "Não"

        # --- CRIAR DATAFRAME ---
        df_oc = pd.DataFrame(st.session_state.db_ocorrencias)
        if "arquivado" not in df_oc.columns:
            df_oc["arquivado"] = "Não"

        # --- FILTRO APENAS ARQUIVADOS ---
        df_arq = df_oc[df_oc["arquivado"] == "Sim"]

        if not df_arq.empty:
            # --- FILTROS ---
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                f_nome = st.text_input("👤 Nome", placeholder="Buscar...", key="arq_nome")
            with f2:
                op_status = ["Todos"] + sorted(df_arq["status"].unique())
                f_status = st.selectbox("📌 Status", op_status, key="arq_status")
            with f3:
                op_motivo = ["Todos"] + sorted(df_arq["motivo"].unique())
                f_motivo = st.selectbox("💡 Motivo", op_motivo, key="arq_motivo")
            with f4:
                f_data = st.date_input("📅 Data", value=None, format="DD/MM/YYYY", key="arq_data")

            # --- APLICAR FILTROS ---
            mask = df_arq["arquivado"] == "Sim"
            if f_nome:
                mask &= df_arq["solicitante"].str.contains(f_nome, case=False, na=False)
            if f_status != "Todos":
                mask &= df_arq["status"] == f_status
            if f_motivo != "Todos":
                mask &= df_arq["motivo"] == f_motivo
            if f_data:
                data_str = f_data.strftime("%Y-%m-%d")
                mask &= df_arq["data"].str.contains(data_str, na=False)

            df_filtrado = df_arq[mask]

            # --- EXIBIÇÃO DOS REGISTROS ---
            if df_filtrado.empty:
                st.info("Nenhum registro encontrado.")
            else:
                for _, o in df_filtrado.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{o['solicitante']}** - Status: :{cor_status(o['status'])}[**{o['status']}**]")
                        st.write(f"Motivo: {o['motivo']} | Data: {o['data']}")

                        if o.get("detalhes"):
                            with st.expander("Ver justificativa"):
                                st.write(o["detalhes"])

                        # Download de anexo, se houver
                        if o.get("anexo"):
                            st.divider()
                            with st.expander("🖼️ Visualizar Documento", expanded=False):
                                # O link do Supabase é exibido diretamente
                                st.image(o["anexo"], caption="Documento Enviado")
                                st.link_button("🔗 Abrir original em nova aba", o["anexo"], use_container_width=True)

                        # Botão para reativar
                        if st.button("📤 Reativar", key=f"re_{o['id']}"):
                            for item in st.session_state.db_ocorrencias:
                                if str(item['id']) == str(o['id']):
                                    item['arquivado'] = "Não"
                            salvar_csv(ARQUIVOS["ocorrencias"], st.session_state.db_ocorrencias)
                            st.success("Ocorrência reativada!")
                            st.rerun()
        else:
            st.info("Nenhum registro arquivado.")
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

    if user['cargo'] in ["Enfermeiro", "Supervisor"]:
        meus_lids = st.session_state.vinculos.get(email_logado, [])

        pendentes = [
            o for o in st.session_state.db_ocorrencias
            if o["status"] == "⏳ Pendente"
            and o["email_solicitante"] in meus_lids
        ]

        qtd_pend = len(pendentes)

        tab_aprov, tab_nova, tab_hist = st.tabs(
            
           [ f"📋 Aprovações ({qtd_pend})",
            "📝 Nova ocorrência",
            "📜 Histórico"
            ]
        )

    else:

        tab_nova, tab_hist = st.tabs(
            ["📝 Nova ocorrência", "📜 Histórico"]
        )

        tab_aprov = None

    # ---------------- APROVAÇÕES ----------------

    if user['cargo'] in ["Enfermeiro", "Supervisor"]:

        with tab_aprov:
            st.header("📋 Gestão de Equipe")
            meus_lids = st.session_state.vinculos.get(email_logado, [])
            pends = [o for o in st.session_state.db_ocorrencias if o['status'] == "⏳ Pendente" and o['email_solicitante'] in meus_lids]

            if pends:
                for oc in pends:
                    with st.container(border=True):
                        c_inf, c_ok, c_no = st.columns([0.6, 0.2, 0.2])

                        texto = f"**{oc['solicitante']}**\n\n📅 {oc.get('data','')}\nMotivo: {oc.get('motivo','')}"
                        if oc.get('horarios'):
                            texto += f"\n🕒 {oc['horarios']}"
                        
                        c_inf.write(texto)

                        if oc.get("detalhes"):
                            with c_inf.expander("Ver justificativa"):
                                st.write(oc["detalhes"])

                        # Visualização e Download do Anexo na Aprovação
                        if oc.get('anexo'):
                            with c_inf:
                                with st.popover("👁️ Visualizar", use_container_width=True):
                                    exibir_anexo(oc["anexo"])

                                try:
                                    with open(oc['anexo'], "rb") as f:
                                        st.download_button(
                                            "📁 Baixar",
                                            f,
                                            file_name=os.path.basename(oc['anexo']),
                                            key=f"dl_apr_{oc['id']}",
                                            use_container_width=True
                                        )
                                except:
                                    st.error("Arquivo não encontrado")

                        # Lógica de Aprovação/Negação
                        if oc['email_solicitante'] != email_logado:
                            if c_ok.button("✅ Aprovar", key=f"apr_ok_{oc['id']}", use_container_width=True):
                                oc['status'] = "✅ Aprovado"
                                oc['aprovado_por'] = user['nome']
                                salvar_csv(ARQUIVOS["ocorrencias"], st.session_state.db_ocorrencias)
                                st.rerun()

                            if c_no.button("❌ Negar", key=f"apr_no_{oc['id']}", use_container_width=True):
                                oc['status'] = "❌ Negado"
                                oc['aprovado_por'] = user['nome']
                                salvar_csv(ARQUIVOS["ocorrencias"], st.session_state.db_ocorrencias)
                                st.rerun()


    # ---------------- NOVA OCORRÊNCIA ----------------

    with tab_nova:

        st.header("📝 Minhas Ocorrências de Ponto")

        mot = st.selectbox(
            "Motivo",
            ["Esquecimento", "Atestado", "Erro no Relógio", "Outro"]
        )

        with st.form("f_ponto", clear_on_submit=True):

            col_a, col_b = st.columns(2)

            data_inicio = col_a.date_input("Data inicial")
            data_fim = col_b.date_input("Data final")

            if mot != "Atestado":

                st.write("Preencha os horários")

                h_cols = st.columns(4)

                h1 = h_cols[0].time_input("Entrada", value=time(0,0), step=60)
                h2 = h_cols[1].time_input("S. Almoço", value=time(0,0), step=60)
                h3 = h_cols[2].time_input("R. Almoço", value=time(0,0), step=60)
                h4 = h_cols[3].time_input("Saída", value=time(0,0), step=60)

            else:

                h1 = h2 = h3 = h4 = None

                st.info("Atestado não precisa de horário")

            just = st.text_area("Justificativa detalhada:")

            anexo_f = st.file_uploader(
                "Comprovante",
                type=["png", "jpg", "jpeg", "pdf"]
            )

            enviar = st.form_submit_button(
                "Enviar Solicitação",
                use_container_width=True
            )

            if enviar:
                if data_fim < data_inicio:
                    st.error("Data final menor que inicial")
                    st.stop()
    
                if mot == "Atestado" and not anexo_f:
                    st.error("Atestado precisa de anexo")
                    st.stop()
    
                if mot != "Atestado":
                    if (h1 == time(0,0) and h2 == time(0,0) and h3 == time(0,0) and h4 == time(0,0)):
                        st.error("Preencha pelo menos um horário")
                        st.stop()
    
                # --- NOVA LÓGICA SUPABASE ---
                
                with st.spinner("Enviando solicitação..."):
                    # 1. Tratamento do Anexo (Storage)
                    link_final_anexo = ""
                    if anexo_f:
                        try:
                            # Nome único para o arquivo
                            nome_arquivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{anexo_f.name}"
                            caminho_storage = f"atestados/{nome_arquivo}"
                            
                            # Upload para o bucket 'anexos'
                            supabase.storage.from_("anexos").upload(caminho_storage, anexo_f.getvalue())
                            
                            # Pega a URL pública
                            link_final_anexo = supabase.storage.from_("anexos").get_public_url(caminho_storage)
                        except Exception as e:
                            st.error(f"Erro ao subir arquivo: {e}")
                            st.stop()
    
                    # 2. Preparação dos Textos (Datas e Horários)
                    if mot == "Atestado":
                        txt_h = ""
                        txt_data = f"{data_inicio} até {data_fim}"
                    else:
                        txt_h = f"{h1.strftime('%H:%M')} | {h2.strftime('%H:%M')} | {h3.strftime('%H:%M')} | {h4.strftime('%H:%M')}"
                        txt_data = str(data_inicio)
    
                    # 3. Montagem do Dicionário para o Supabase
                    # Ajustado conforme as colunas do seu print
                    nova_ocorrencia = {
                        "solicitante": user['nome'],
                        "email_solicita": email_logado,
                        "data": txt_data,
                        "horarios": txt_h,
                        "status": "⏳ Pendente",
                        "arquivado": "Não",
                        "motivo": mot,
                        "detalhes": just,
                        "anexo": link_final_anexo,
                        "aprovado_por": ""
                    }
    
                    # 4. Inserção no Banco de Dados
                    try:
                        supabase.table("ocorrencias").insert(nova_ocorrencia).execute()
                        
                        # Atualiza a lista na memória para refletir a mudança
                        res = supabase.table("ocorrencias").select("*").execute()
                        st.session_state.db_ocorrencias = res.data
                        
                        st.success("Solicitação enviada para o banco de dados!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar no Supabase: {e}")


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
                    if o.get('status') == "⏳ Pendente":
                        if col_btn.button("🗑️ Cancelar", key=f"canc_user_{o['id']}", help="Remover solicitação pendente", use_container_width=True):
                            st.session_state.db_ocorrencias = [item for item in st.session_state.db_ocorrencias if str(item['id']) != str(o['id'])]
                            salvar_csv(ARQUIVOS["ocorrencias"], st.session_state.db_ocorrencias)
                            st.success("Solicitação cancelada.")
                            st.rerun()
                    else:
                        # Se já foi aprovado ou negado, o botão some e aparece o cadeado
                        col_btn.write("🔒 *Processado*")

                    # Download do anexo
                    if o.get("anexo"):
                        try:
                            with open(o["anexo"], "rb") as f:
                                st.download_button("📁 Baixar Anexo", f, file_name=os.path.basename(o["anexo"]), key=f"h_{o['id']}")
                        except:
                            st.warning("Anexo não encontrado")
        else:

            st.info("Você ainda não possui ocorrências registradas.")




















