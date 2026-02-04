import streamlit as st
import pandas as pd
import glob
import plotly.express as px

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

# --- Funções Auxiliares (Session State) ---
# Funções para gerenciar os botões de "Selecionar Tudo/Limpar"
def selecionar_tudo(chave, opcoes):
    st.session_state[chave] = opcoes

def limpar_tudo(chave):
    st.session_state[chave] = []

# --- Funções de Carregamento ---
@st.cache_data
def load_data():
    # 1. Carregar dados das Rodadas
    rodada_files = glob.glob("rodada-*.csv")
    if not rodada_files:
        st.error("⚠️ Nenhum arquivo 'rodada-*.csv' encontrado.")
        return pd.DataFrame(), pd.DataFrame()
    
    dfs = []
    for f in rodada_files:
        try:
            dfs.append(pd.read_csv(f))
        except Exception as e:
            st.warning(f"Erro ao ler {f}: {e}")
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    # 2. Carregar dados de Confrontos
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos = pd.DataFrame()
    
    if confronto_files:
        try:
            df_jogos = pd.read_csv(confronto_files[0])
            # Ajuste de Mando
            df_jogos['Mando_Padrao'] = df_jogos['Mando'].apply(
                lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA'
            )
        except Exception as e:
            st.warning(f"Erro ao ler arquivo de confrontos: {e}")
    
    return df_main, df_jogos

df, df_jogos = load_data()

# --- Processamento ---
if not df.empty:
    # Cruzamento com Jogos
    if not df_jogos.empty:
        df['atletas.rodada_id'] = df['atletas.rodada_id'].astype(int)
        df['atletas.clube_id'] = df['atletas.clube_id'].astype(int)
        df_jogos['rodada_id'] = df_jogos['rodada_id'].astype(int)
        df_jogos['clube_id'] = df_jogos['clube_id'].astype(int)

        df = pd.merge(
            df, 
            df_jogos[['rodada_id', 'clube_id', 'Mando_Padrao', 'Adversario']], 
            left_on=['atletas.rodada_id', 'atletas.clube_id'], 
            right_on=['rodada_id', 'clube_id'], 
            how='left'
        )
        df['Mando_Padrao'] = df['Mando_Padrao'].fillna('N/A')
    else:
        df['Mando_Padrao'] = 'N/A'

    # Mapeamentos e Tratamentos
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    scout_cols = ['G', 'A', 'DS', 'FC', 'FS', 'CA', 'FD', 'FF', 'FT', 'SG', 'DE', 'DP', 'GS']
    for col in scout_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)

    # Cálculos
    df['media_basica'] = df['atletas.pontos_num'] - (8 * df['G']) - (5 * df['A'])
    
    # CORREÇÃO DO ERRO VISUAL: Criar coluna positiva para tamanho da bolha
    # Se media_basica < 0.1, definimos como 0.1 para o gráfico não quebrar
    df['tamanho_visual'] = df['media_basica'].apply(lambda x: max(0.1, x))

    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']

    # --- Sidebar (Filtros com Botões) ---
    st.sidebar.header("🔍 Filtros")

    # Listas de opções únicas
    all_rodadas = sorted(df['atletas.rodada_id'].unique())
    all_clubes = sorted(df['atletas.clube.id.full.name'].unique())
    all_posicoes = sorted(df['posicao_nome'].unique())

    # --- Filtro: Rodada ---
    if 'sel_rodada' not in st.session_state: st.session_state['sel_rodada'] = all_rodadas
    
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Todos", key="btn_all_rodada"): selecionar_tudo('sel_rodada', all_rodadas)
    if c2.button("Limpar", key="btn_clear_rodada"): limpar_tudo('sel_rodada')
    
    sel_rodada = st.sidebar.multiselect("Rodada", all_rodadas, key='sel_rodada')

    # --- Filtro: Clube ---
    if 'sel_clube' not in st.session_state: st.session_state['sel_clube'] = [] # Começa vazio ou cheio conforme preferencia
    
    c3, c4 = st.sidebar.columns(2)
    if c3.button("Todos", key="btn_all_clube"): selecionar_tudo('sel_clube', all_clubes)
    if c4.button("Limpar", key="btn_clear_clube"): limpar_tudo('sel_clube')

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, key='sel_clube')

    # --- Filtro: Posição ---
    if 'sel_posicao' not in st.session_state: st.session_state['sel_posicao'] = []

    c5, c6 = st.sidebar.columns(2)
    if c5.button("Todos", key="btn_all_pos"): selecionar_tudo('sel_posicao', all_posicoes)
    if c6.button("Limpar", key="btn_clear_pos"): limpar_tudo('sel_posicao')

    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, key='sel_posicao')
    
    # Outros filtros simples
    opcoes_mando = ['CASA', 'FORA']
    sel_mando = st.sidebar.multiselect("Mando", opcoes_mando, default=opcoes_mando)
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # --- Aplicação dos Filtros ---
    df_filtrado = df[df['atletas.rodada_id'].isin(sel_rodada)]
    
    if sel_clube:
        df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao:
        df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if 'Mando_Padrao' in df_filtrado.columns and sel_mando:
        df_filtrado = df_filtrado[df_filtrado['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram:
        df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]

    # --- Interface Principal ---
    
    # Proteção contra DataFrame vazio após filtros
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado encontrado com os filtros selecionados.")
    else:
        # KPIs Rápidos
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Maior Pontuador", f"{df_filtrado['atletas.pontos_num'].max()} pts")
        col2.metric("Média Geral", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
        
        # Verificando se existem dados antes de pegar o IDMAX
        if not df_filtrado['DS'].empty and df_filtrado['DS'].sum() > 0:
            rei_ds = df_filtrado.loc[df_filtrado['DS'].idxmax()]
            col3.metric("Rei dos Desarmes", f"{rei_ds['atletas.apelido']} ({int(rei_ds['DS'])})")
        else:
            col3.metric("Rei dos Desarmes", "-")
            
        col4.metric("Qtd. Jogadores", f"{len(df_filtrado)}")

        st.markdown("---")

        tab_scouts, tab_valorizacao, tab_tabela = st.tabs(["📊 Análise de Scouts", "💰 Valorização & Preço", "📋 Tabela Completa"])

        with tab_scouts:
            st.subheader("Desempenho: Dentro de Casa vs Fora de Casa")
            if 'Mando_Padrao' in df_filtrado.columns and not df_filtrado['Mando_Padrao'].isna().all():
                grupo_mando = df_filtrado.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                
                c1, c2 = st.columns(2)
                with c1:
                    fig_of = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', 
                                    color='Mando_Padrao', barmode='group',
                                    title="Ataque: Média de Scouts",
                                    color_discrete_map={'CASA': '#00CC96', 'FORA': '#EF553B'})
                    st.plotly_chart(fig_of, use_container_width=True)
                
                with c2:
                    fig_def = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_defensivos_total', 
                                    color='Mando_Padrao', barmode='group',
                                    title="Defesa: Média de Scouts",
                                    color_discrete_map={'CASA': '#00CC96', 'FORA': '#EF553B'})
                    st.plotly_chart(fig_def, use_container_width=True)
            else:
                st.info("Dados de mando não disponíveis para o filtro atual.")

        with tab_valorizacao:
            st.subheader("Oportunidades de Mercado")
            # CORREÇÃO: Usando 'tamanho_visual' em vez de 'media_basica' para o size
            fig_val = px.scatter(
                df_filtrado, 
                x='atletas.preco_num', 
                y='atletas.pontos_num',
                color='posicao_nome',
                size='tamanho_visual', # <--- AQUI ESTAVA O ERRO (Agora usa a coluna tratada)
                hover_data=['atletas.apelido', 'atletas.clube.id.full.name', 'media_basica'],
                title="Quem entrega mais pontos por C$ investido? (Tamanho da bolha = Média Básica)"
            )
            st.plotly_chart(fig_val, use_container_width=True)

        with tab_tabela:
            st.subheader("Dados Detalhados")
            cols_view = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'Mando_Padrao', 
                         'atletas.preco_num', 'atletas.pontos_num', 'media_basica', 
                         'G', 'A', 'DS', 'FS', 'FF', 'FD']
            
            # Filtra apenas colunas que existem
            cols_existentes = [c for c in cols_view if c in df_filtrado.columns]
            
            st.dataframe(
                df_filtrado[cols_existentes].sort_values('media_basica', ascending=False),
                use_container_width=True,
                hide_index=True
            )

else:
    st.info("Aguardando carregamento dos dados...")
