import streamlit as st
import pandas as pd
import glob
import plotly.express as px

# --- Configurações da Página ---
st.set_page_config(page_title="Cartola FC 2026 Analytics", layout="wide", page_icon="⚽")

# Estilo CSS customizado para deixar mais "clean"
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("⚽ Dashboard Analítico - Cartola FC 2026")

# --- Funções de Carregamento ---
@st.cache_data
def load_data():
    # 1. Carregar JOGADORES (Rodadas)
    rodada_files = glob.glob("rodada-*.csv")
    if not rodada_files:
        st.error("⚠️ Nenhum arquivo 'rodada-*.csv' encontrado.")
        return pd.DataFrame(), pd.DataFrame()
    
    dfs = []
    for f in rodada_files:
        try:
            temp_df = pd.read_csv(f)
            dfs.append(temp_df)
        except Exception as e:
            st.warning(f"Erro ao ler {f}: {e}")
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    # 2. Carregar CONFRONTOS (Jogos) - CORREÇÃO AQUI
    # Agora carregamos TODOS os arquivos de confronto, não apenas o [0]
    confronto_files = glob.glob("confrontos_*.csv")
    dfs_jogos = []
    
    if confronto_files:
        for f in confronto_files:
            try:
                temp_jogos = pd.read_csv(f)
                dfs_jogos.append(temp_jogos)
            except Exception as e:
                st.warning(f"Erro ao ler confrontos {f}: {e}")
    
    if dfs_jogos:
        df_jogos = pd.concat(dfs_jogos, ignore_index=True)
        # Cria coluna padronizada de mando
        df_jogos['Mando_Padrao'] = df_jogos['Mando'].apply(
            lambda x: 'CASA' if isinstance(x, str) and 'Casa' in x and 'Fora' not in x else 'FORA'
        )
    else:
        df_jogos = pd.DataFrame()
    
    return df_main, df_jogos

# Carrega os dados
df, df_jogos = load_data()

# --- Pré-Processamento e Cruzamento ---
if not df.empty:
    # Tratamento de IDs para garantir o Merge (Converte tudo para numérico seguro)
    cols_id_df = ['atletas.rodada_id', 'atletas.clube_id']
    cols_id_jogos = ['rodada_id', 'clube_id']

    # Força conversão para numérico (trata erros como NaN e preenche com 0)
    for col in cols_id_df:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    if not df_jogos.empty:
        for col in cols_id_jogos:
            df_jogos[col] = pd.to_numeric(df_jogos[col], errors='coerce').fillna(0).astype(int)

        # Cruzamento (Left Join)
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

    # Mapeamento de Posições
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # Tratamento de Scouts (Substituir NaN por 0)
    scout_cols = ['G', 'A', 'DS', 'FC', 'FS', 'CA', 'FD', 'FF', 'FT', 'SG', 'DE', 'DP', 'GS']
    for col in scout_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)

    # Cálculos Avançados
    df['media_basica'] = df['atletas.pontos_num'] - (8 * df['G']) - (5 * df['A'])
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']
    
    # Tamanho visual para o gráfico de bolhas (evita bolhas negativas sumindo)
    df['tamanho_visual'] = df['atletas.pontos_num'].apply(lambda x: max(2, x + 5)) 

    # --- SIDEBAR DE FILTROS ---
    st.sidebar.header("🔍 Filtros de Análise")

    # 1. Filtro de Rodada
    lista_rodadas = sorted(df['atletas.rodada_id'].unique())
    if lista_rodadas:
        sel_rodada = st.sidebar.select_slider("Selecione a Rodada", options=lista_rodadas, value=lista_rodadas[-1])
        df_filtrado = df[df['atletas.rodada_id'] == sel_rodada]
    else:
        df_filtrado = df

    # 2. Filtro de Posição
    all_posicoes = sorted(df_filtrado['posicao_nome'].dropna().unique())
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    if sel_posicao:
        df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]

    # 3. Filtro de Clube
    all_clubes = sorted(df_filtrado['atletas.clube.id.full.name'].dropna().unique())
    sel_clube = st.sidebar.multiselect("Clube", all_clubes)
    if sel_clube:
        df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]

    # 4. Apenas quem jogou
    if st.sidebar.checkbox("Apenas quem entrou em campo?", value=True):
        df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]

    # --- DASHBOARD PRINCIPAL ---
    
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum jogador encontrado com esses filtros.")
    else:
        # Métricas de Topo
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Maior Pontuador", f"{df_filtrado['atletas.pontos_num'].max()} pts")
        col2.metric("Média da Rodada", f"{df_filtrado['atletas.pontos_num'].mean():.2f} pts")
        col3.metric("Gols na Rodada", f"{int(df_filtrado['G'].sum())}")
        col4.metric("Assistências", f"{int(df_filtrado['A'].sum())}")

        st.divider()

        # Abas
        tab_grafico, tab_scouts, tab_tabela = st.tabs(["📊 Visão Gráfica", "🔎 Scouts Detalhados", "📋 Tabela"])

        with tab_grafico:
            st.subheader("Dispersão: Preço x Pontuação (Quem entregou mais?)")
            st.caption("Eixo X: Preço | Eixo Y: Pontos | Cor: Posição | Tamanho: Pontuação")
            
            # GRÁFICO ESTILO 'DATAVIZ' COLORIDO
            fig_scatter = px.scatter(
                df_filtrado,
                x="atletas.preco_num",
                y="atletas.pontos_num",
                color="posicao_nome",  # Legenda colorida por posição
                size="tamanho_visual", # Bolhas maiores para quem pontuou mais
                hover_data=["atletas.apelido", "atletas.clube.id.full.name", "G", "A"],
                title=f"Performance na Rodada {sel_rodada}",
                template="plotly_white", # Fundo branco limpo
                color_discrete_sequence=px.colors.qualitative.Bold # Cores fortes
            )
            # Linha de média
            media_y = df_filtrado['atletas.pontos_num'].mean()
            fig_scatter.add_hline(y=media_y, line_dash="dot", annotation_text="Média da Rodada", annotation_position="bottom right")
            
            st.plotly_chart(fig_scatter, use_container_width=True)

            # Gráfico de Barras por Clube
            st.subheader("Média de Pontos por Clube")
            df_clube = df_filtrado.groupby('atletas.clube.id.full.name')['atletas.pontos_num'].mean().reset_index().sort_values('atletas.pontos_num', ascending=False)
            
            fig_bar = px.bar(
                df_clube,
                x='atletas.clube.id.full.name',
                y='atletas.pontos_num',
                color='atletas.pontos_num',
                color_continuous_scale='Viridis', # Degradê bonito
                text_auto='.1f',
                title="Eficiência dos Clubes na Rodada"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab_scouts:
            st.subheader("Líderes de Estatísticas")
            c_s1, c_s2 = st.columns(2)
            
            # Top Finalizadores
            top_fin = df_filtrado.nlargest(5, 'finalizacoes_total')[['atletas.apelido', 'atletas.clube.id.full.name', 'finalizacoes_total', 'G']]
            c_s1.markdown("##### 🚀 Top Finalizadores")
            c_s1.table(top_fin.set_index('atletas.apelido'))

            # Top Desarmes
            top_ds = df_filtrado.nlargest(5, 'DS')[['atletas.apelido', 'atletas.clube.id.full.name', 'DS', 'SG']]
            c_s2.markdown("##### 🛡️ Top Desarmes")
            c_s2.table(top_ds.set_index('atletas.apelido'))

        with tab_tabela:
            st.dataframe(
                df_filtrado[['atletas.apelido', 'posicao_nome', 'atletas.clube.id.full.name', 
                             'atletas.preco_num', 'atletas.pontos_num', 'atletas.variacao_num', 
                             'G', 'A', 'DS', 'SG', 'Mando_Padrao']].sort_values('atletas.pontos_num', ascending=False),
                use_container_width=True,
                column_config={
                    "atletas.preco_num": st.column_config.NumberColumn("Preço (C$)", format="C$ %.2f"),
                    "atletas.pontos_num": st.column_config.NumberColumn("Pontos", format="%.1f"),
                    "atletas.variacao_num": st.column_config.NumberColumn("Var.", format="%.2f"),
                }
            )

else:
    st.info("Aguardando dados...")
