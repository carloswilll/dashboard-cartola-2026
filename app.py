import streamlit as st
import pandas as pd
import glob
import plotly.express as px
import plotly.graph_objects as go

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

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

    # 2. Carregar dados de Confrontos (Jogos)
    # Procura qualquer arquivo que comece com 'confrontos_'
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos = pd.DataFrame()
    
    if confronto_files:
        try:
            # Pega o primeiro que encontrar (ou concatena se tiver vários)
            df_jogos = pd.read_csv(confronto_files[0])
            # Padroniza coluna de Mando para 'CASA' ou 'FORA'
            # Seu arquivo tem "Casa" e "Fora de Casa"
            df_jogos['Mando_Padrao'] = df_jogos['Mando'].apply(lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA')
        except Exception as e:
            st.warning(f"Erro ao ler arquivo de confrontos: {e}")
    
    return df_main, df_jogos

df, df_jogos = load_data()

# --- Processamento e Cruzamento de Dados ---
if not df.empty:
    # 1. Cruzar com a tabela de Jogos (se existir)
    if not df_jogos.empty:
        # Garante que os IDs sejam do mesmo tipo (int)
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
        st.info("ℹ️ Arquivo de confrontos não detectado. A análise Casa/Fora ficará desativada.")

    # 2. Mapeamento de Posições
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # 3. Tratamento de Nulos nos Scouts
    scout_cols = ['G', 'A', 'DS', 'FC', 'FS', 'CA', 'FD', 'FF', 'FT', 'SG', 'DE', 'DP', 'GS']
    for col in scout_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)

    # 4. Cálculos Avançados (KPIs)
    # Média Básica: Pontos - (8*Gols + 5*Assistências)
    df['media_basica'] = df['atletas.pontos_num'] - (8 * df['G']) - (5 * df['A'])
    
    # Scouts Agrupados
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']

    # --- Sidebar (Filtros) ---
    st.sidebar.header("🔍 Filtros")
    
    # Filtro de Rodada
    rodadas_disp = sorted(df['atletas.rodada_id'].unique())
    sel_rodada = st.sidebar.multiselect("Rodada", rodadas_disp, default=rodadas_disp)
    
    # Filtro Casa/Fora
    opcoes_mando = ['CASA', 'FORA']
    sel_mando = st.sidebar.multiselect("Mando de Campo", opcoes_mando, default=opcoes_mando)
    
    # Outros Filtros
    sel_clube = st.sidebar.multiselect("Clube", sorted(df['atletas.clube.id.full.name'].unique()))
    sel_posicao = st.sidebar.multiselect("Posição", sorted(df['posicao_nome'].unique()))
    
    # Slider de Jogos Jogados (se houver essa info acumulada, senão usa filtro simples)
    # Como o dado é por rodada, vamos filtrar por status "Provável" ou "Entrou em campo"
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # --- Aplicar Filtros ---
    df_filtrado = df[df['atletas.rodada_id'].isin(sel_rodada)]
    if 'Mando_Padrao' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['Mando_Padrao'].isin(sel_mando)]
    if sel_clube:
        df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao:
        df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if somente_jogaram:
        df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]

    # --- Interface Principal ---

    # 1. KPIs Rápidos
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Maior Pontuador", f"{df_filtrado['atletas.pontos_num'].max()} pts")
    col2.metric("Média de Pontos (Filtro)", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
    col3.metric("Rei dos Desarmes", f"{df_filtrado.loc[df_filtrado['DS'].idxmax()]['atletas.apelido']} ({int(df_filtrado['DS'].max())})")
    col4.metric("Rei da Média Básica", f"{df_filtrado.loc[df_filtrado['media_basica'].idxmax()]['atletas.apelido']} ({df_filtrado['media_basica'].max():.1f})")

    st.markdown("---")

    # 2. Abas de Análise
    tab_scouts, tab_valorizacao, tab_tabela = st.tabs(["📊 Análise de Scouts (Casa vs Fora)", "💰 Valorização & Preço", "📋 Tabela Completa"])

    with tab_scouts:
        st.subheader("Desempenho: Dentro de Casa vs Fora de Casa")
        
        # Agrupa dados para o gráfico
        if 'Mando_Padrao' in df_filtrado.columns:
            grupo_mando = df_filtrado.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Média de Scouts OFENSIVOS por Jogo**")
                fig_of = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', 
                                color='Mando_Padrao', barmode='group',
                                title="Ataque: Mandante vs Visitante",
                                labels={'scouts_ofensivos_total': 'Média Scouts Ofensivos', 'atletas.clube.id.full.name': 'Clube'})
                st.plotly_chart(fig_of, use_container_width=True)
            
            with c2:
                st.markdown("**Média de Scouts DEFENSIVOS por Jogo**")
                fig_def = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_defensivos_total', 
                                color='Mando_Padrao', barmode='group',
                                title="Defesa: Mandante vs Visitante",
                                labels={'scouts_defensivos_total': 'Média Scouts Defensivos', 'atletas.clube.id.full.name': 'Clube'})
                st.plotly_chart(fig_def, use_container_width=True)
        else:
            st.warning("Dados de mando de campo não disponíveis.")

    with tab_valorizacao:
        st.subheader("Oportunidades de Mercado")
        # Scatter plot: Eixo X = Preço, Eixo Y = Pontuação
        # Cor = Posição, Tamanho = Média Básica
        fig_val = px.scatter(
            df_filtrado, 
            x='atletas.preco_num', 
            y='atletas.pontos_num',
            color='posicao_nome',
            size='media_basica',
            hover_data=['atletas.apelido', 'atletas.clube.id.full.name', 'Mando_Padrao'],
            title="Quem entrega mais pontos por C$ investido? (Tamanho da bolha = Média Básica)"
        )
        st.plotly_chart(fig_val, use_container_width=True)

    with tab_tabela:
        st.subheader("Dados Detalhados")
        # Seleção de colunas para exibir
        cols_view = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'Mando_Padrao', 
                     'atletas.preco_num', 'atletas.pontos_num', 'media_basica', 
                     'G', 'A', 'DS', 'FS', 'FF', 'FD']
        
        st.dataframe(
            df_filtrado[cols_view].sort_values('media_basica', ascending=False),
            use_container_width=True,
            hide_index=True
        )

else:
    st.info("Aguardando carregamento dos dados...")