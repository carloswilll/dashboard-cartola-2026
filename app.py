import streamlit as st
import pandas as pd
import glob
import plotly.express as px
import os

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

# --- CSS Personalizado (Opcional) ---
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- Funções Auxiliares (Session State) ---
def selecionar_tudo(chave, opcoes):
    st.session_state[chave] = opcoes

def limpar_tudo(chave):
    st.session_state[chave] = []

# --- Funções de Carregamento ---
@st.cache_data
def load_data():
    # Procura arquivos CSV recursivamente na pasta atual e subpastas
    # Isso resolve o problema se os arquivos estiverem dentro de 'dashboard-cartola-2026-main'
    all_csvs = glob.glob("**/*.csv", recursive=True)
    
    rodada_files = [f for f in all_csvs if "rodada-" in f and "csv" in f]
    confronto_files = [f for f in all_csvs if "confrontos" in f and "csv" in f]

    # Debug: Mostrar arquivos encontrados na sidebar (ajuda a identificar erro de caminho)
    with st.sidebar.expander("📂 Diagnóstico de Arquivos (Debug)", expanded=False):
        st.write("Arquivos de Rodada encontrados:", rodada_files)
        st.write("Arquivos de Confronto encontrados:", confronto_files)

    if not rodada_files:
        return pd.DataFrame(), pd.DataFrame()
    
    # 1. Carregar e Concatenar Dados das Rodadas
    dfs = []
    for f in rodada_files:
        try:
            temp_df = pd.read_csv(f)
            # Normalização simples de colunas caso haja diferenças sutis
            dfs.append(temp_df)
        except Exception as e:
            st.warning(f"Erro ao ler {f}: {e}")
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    # Tratamento inicial de nulos em colunas numéricas essenciais
    cols_to_fix = ['atletas.rodada_id', 'atletas.clube_id', 'atletas.pontos_num', 'atletas.preco_num']
    for col in cols_to_fix:
        if col in df_main.columns:
            df_main[col] = pd.to_numeric(df_main[col], errors='coerce').fillna(0)

    # 2. Carregar dados de Confrontos
    df_jogos = pd.DataFrame()
    if confronto_files:
        try:
            # Carrega todos os arquivos de confronto se houver mais de um
            dfs_jogos = [pd.read_csv(f) for f in confronto_files]
            df_jogos = pd.concat(dfs_jogos, ignore_index=True)
            
            # Normaliza nomes de colunas para garantir o merge
            if 'Mando' in df_jogos.columns:
                df_jogos['Mando_Padrao'] = df_jogos['Mando'].apply(
                    lambda x: 'CASA' if isinstance(x, str) and 'Casa' in x and 'Fora' not in x else 'FORA'
                )
        except Exception as e:
            st.warning(f"Erro ao ler arquivo de confrontos: {e}")
    
    return df_main, df_jogos

# Carrega os dados
df, df_jogos = load_data()

# --- Processamento ---
if not df.empty:
    # --- 1. Cruzamento com Jogos (Merge) ---
    if not df_jogos.empty:
        # Garante tipos compatíveis para o merge
        df['join_rodada'] = df['atletas.rodada_id'].astype(int)
        df['join_clube'] = df['atletas.clube_id'].astype(int)
        
        df_jogos['join_rodada'] = df_jogos['rodada_id'].astype(int)
        df_jogos['join_clube'] = df_jogos['clube_id'].astype(int)

        df = pd.merge(
            df, 
            df_jogos[['join_rodada', 'join_clube', 'Mando_Padrao', 'Adversario']], 
            left_on=['join_rodada', 'join_clube'], 
            right_on=['join_rodada', 'join_clube'], 
            how='left'
        )
        df['Mando_Padrao'] = df['Mando_Padrao'].fillna('N/A')
        df['Adversario'] = df['Adversario'].fillna('-')
    else:
        df['Mando_Padrao'] = 'N/A'
        df['Adversario'] = '-'

    # --- 2. Mapeamentos e Tratamentos de Scouts ---
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    if 'atletas.posicao_id' in df.columns:
        df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map).fillna('Outros')
    else:
        df['posicao_nome'] = 'Desconhecido'

    # Lista completa de scouts possíveis
    scout_cols = ['G', 'A', 'DS', 'FC', 'FS', 'CA', 'FD', 'FF', 'FT', 'SG', 'DE', 'DP', 'GS', 'V', 'I', 'PS', 'CV', 'GC']
    
    # Garante que as colunas existam e sejam float, preenchendo nulos com 0
    for col in scout_cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- 3. Cálculos Avançados ---
    # Média Básica (Pontos - Gols - Assistências - SG para defesa)
    # Ajuste simples: Pontos - (Gols * 8) - (Assist * 5). Ajuste conforme regra 2026 se mudar.
    df['media_basica'] = df['atletas.pontos_num'] - (8 * df['G']) - (5 * df['A'])
    
    # Scouts Agregados
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']
    
    # Coluna para tamanho visual nos gráficos (evita bolhas negativas ou zero)
    df['tamanho_visual'] = df['atletas.pontos_num'].apply(lambda x: max(1.0, x))

    # --- Sidebar (Filtros) ---
    st.sidebar.header("🔍 Filtros")

    # Filtro de Rodada
    min_r = int(df['atletas.rodada_id'].min())
    max_r = int(df['atletas.rodada_id'].max())
    if min_r == max_r:
        sel_rodada_range = (min_r, max_r)
        st.sidebar.info(f"Dados apenas da Rodada {min_r}")
    else:
        sel_rodada_range = st.sidebar.slider("Rodadas", min_r, max_r, (min_r, max_r))

    # Filtros Categóricos
    all_clubes = sorted(df['atletas.clube.id.full.name'].astype(str).unique())
    all_posicoes = sorted(df['posicao_nome'].astype(str).unique())

    # Clube
    if 'sel_clube' not in st.session_state: st.session_state['sel_clube'] = []
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Todos", key="clube_all"): selecionar_tudo('sel_clube', all_clubes)
    if c2.button("Limpar", key="clube_none"): limpar_tudo('sel_clube')
    sel_clube = st.sidebar.multiselect("Clube", all_clubes, key='sel_clube')

    # Posição
    if 'sel_posicao' not in st.session_state: st.session_state['sel_posicao'] = []
    c3, c4 = st.sidebar.columns(2)
    if c3.button("Todos", key="pos_all"): selecionar_tudo('sel_posicao', all_posicoes)
    if c4.button("Limpar", key="pos_none"): limpar_tudo('sel_posicao')
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, key='sel_posicao')
    
    # Checkbox Jogou
    somente_jogaram = st.sidebar.checkbox("Apenas quem pontuou (!= 0)?", value=False)

    # --- Aplicação dos Filtros ---
    df_filtrado = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]
    
    if sel_clube:
        df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao:
        df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if somente_jogaram:
        df_filtrado = df_filtrado[df_filtrado['atletas.pontos_num'] != 0]

    # --- Interface Principal ---
    
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado encontrado com os filtros selecionados.")
    else:
        # KPIs Gerais
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Média de Pontos", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
        k2.metric("Maior Pontuação", f"{df_filtrado['atletas.pontos_num'].max():.2f}")
        k3.metric("Total de Gols", f"{int(df_filtrado['G'].sum())}")
        k4.metric("Total de SG", f"{int(df_filtrado['SG'].sum())}")

        st.markdown("---")

        # Abas
        tab_destaques, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🏆 Destaques", 
            "🛡️ Times", 
            "📊 Scouts", 
            "💰 Valorização", 
            "📋 Dados"
        ])

        # --- ABA 1: DESTAQUES ---
        with tab_destaques:
            col_d1, col_d2 = st.columns(2)
            
            with col_d1:
                st.subheader("Top Pontuadores")
                top_players = df_filtrado.nlargest(10, 'atletas.pontos_num')
                fig_top = px.bar(
                    top_players, 
                    x='atletas.pontos_num', 
                    y='atletas.apelido', 
                    orientation='h',
                    color='atletas.clube.id.full.name',
                    text_auto='.1f',
                    title="Maiores Pontuações no Período"
                )
                fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_top, use_container_width=True)

            with col_d2:
                st.subheader("Reis dos Desarmes")
                top_ds = df_filtrado.nlargest(10, 'DS')
                fig_ds = px.bar(
                    top_ds, 
                    x='DS', 
                    y='atletas.apelido', 
                    orientation='h',
                    color='posicao_nome',
                    text_auto=True,
                    title="Jogadores com mais Desarmes"
                )
                fig_ds.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_ds, use_container_width=True)

        # --- ABA 2: TIMES ---
        with tab_times:
            club_stats = df_filtrado.groupby('atletas.clube.id.full.name').agg({
                'atletas.pontos_num': 'mean',
                'finalizacoes_total': 'sum',
                'DS': 'sum',
                'SG': 'sum'
            }).reset_index()
            
            st.subheader("Média de Pontos por Clube")
            fig_times = px.bar(
                club_stats.sort_values('atletas.pontos_num', ascending=False),
                x='atletas.clube.id.full.name',
                y='atletas.pontos_num',
                color='atletas.pontos_num',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig_times, use_container_width=True)

        # --- ABA 3: SCOUTS ---
        with tab_scouts:
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown("**Dispersão: Finalizações x Gols**")
                fig_scout1 = px.scatter(
                    df_filtrado, x='finalizacoes_total', y='G',
                    color='posicao_nome', hover_data=['atletas.apelido'],
                    size='tamanho_visual'
                )
                st.plotly_chart(fig_scout1, use_container_width=True)
            
            with col_s2:
                st.markdown("**Dispersão: Desarmes x SG**")
                fig_scout2 = px.scatter(
                    df_filtrado, x='DS', y='SG',
                    color='posicao_nome', hover_data=['atletas.apelido'],
                    size='tamanho_visual'
                )
                st.plotly_chart(fig_scout2, use_container_width=True)

        # --- ABA 4: VALORIZAÇÃO ---
        with tab_valorizacao:
            st.subheader("Preço x Pontos")
            fig_val = px.scatter(
                df_filtrado,
                x='atletas.preco_num',
                y='atletas.pontos_num',
                color='posicao_nome',
                size='tamanho_visual',
                hover_data=['atletas.apelido', 'atletas.clube.id.full.name'],
                labels={'atletas.preco_num': 'Preço (C$)', 'atletas.pontos_num': 'Pontuação'}
            )
            st.plotly_chart(fig_val, use_container_width=True)

        # --- ABA 5: TABELA ---
        with tab_tabela:
            st.dataframe(
                df_filtrado[[
                    'atletas.rodada_id', 'atletas.apelido', 'atletas.clube.id.full.name', 
                    'posicao_nome', 'atletas.pontos_num', 'atletas.preco_num', 
                    'G', 'A', 'DS', 'SG', 'Adversario', 'Mando_Padrao'
                ]].sort_values('atletas.pontos_num', ascending=False),
                use_container_width=True,
                hide_index=True
            )

else:
    st.error("❌ Não foi possível carregar os dados. Verifique se os arquivos CSV estão na pasta do projeto.")
    st.info("Dica: Os arquivos devem ter 'rodada-' ou 'confrontos' no nome.")
