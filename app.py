import streamlit as st
import pandas as pd
import glob
import plotly.express as px

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

# --- Funções Auxiliares (Session State) ---
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
    df['tamanho_visual'] = df['media_basica'].apply(lambda x: max(0.1, x)) # Proteção visual

    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # --- Sidebar (Filtros) ---
    st.sidebar.header("🔍 Filtros Principais")

    # 1. Filtro Deslizante de Rodada
    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    if min_rodada == max_rodada:
        sel_rodada_range = (min_rodada, max_rodada)
        st.sidebar.caption(f"Apenas dados da Rodada {min_rodada} disponíveis.")
    else:
        sel_rodada_range = st.sidebar.slider("Intervalo de Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))

    # 2. Filtro Deslizante de Preço
    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Faixa de Preço (C$)", min_preco, max_preco, (min_preco, max_preco))

    # 3. Filtro Deslizante de Pontuação
    min_pts, max_pts = float(df['atletas.pontos_num'].min()), float(df['atletas.pontos_num'].max())
    sel_pts_range = st.sidebar.slider("Faixa de Pontuação", min_pts, max_pts, (min_pts, max_pts))
    
    st.sidebar.markdown("---")
    st.sidebar.header("📌 Filtros Categóricos")

    # Filtros Categóricos (Clube/Posição)
    all_clubes = sorted(df['atletas.clube.id.full.name'].unique())
    all_posicoes = sorted(df['posicao_nome'].unique())

    # Clube
    if 'sel_clube' not in st.session_state: st.session_state['sel_clube'] = []
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Todos", key="btn_all_clube"): selecionar_tudo('sel_clube', all_clubes)
    if c2.button("Limpar", key="btn_clear_clube"): limpar_tudo('sel_clube')
    sel_clube = st.sidebar.multiselect("Clube", all_clubes, key='sel_clube')

    # Posição
    if 'sel_posicao' not in st.session_state: st.session_state['sel_posicao'] = []
    c3, c4 = st.sidebar.columns(2)
    if c3.button("Todos", key="btn_all_pos"): selecionar_tudo('sel_posicao', all_posicoes)
    if c4.button("Limpar", key="btn_clear_pos"): limpar_tudo('sel_posicao')
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, key='sel_posicao')
    
    # Mando e Jogou
    opcoes_mando = ['CASA', 'FORA']
    sel_mando = st.sidebar.multiselect("Mando", opcoes_mando, default=opcoes_mando)
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # --- Aplicação dos Filtros ---
    # Filtra primeiro pelos sliders numéricos
    df_filtrado = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1]) &
        (df['atletas.preco_num'] >= sel_preco_range[0]) &
        (df['atletas.preco_num'] <= sel_preco_range[1]) &
        (df['atletas.pontos_num'] >= sel_pts_range[0]) &
        (df['atletas.pontos_num'] <= sel_pts_range[1])
    ]
    
    # Filtra pelos categóricos
    if sel_clube:
        df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao:
        df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if 'Mando_Padrao' in df_filtrado.columns and sel_mando:
        df_filtrado = df_filtrado[df_filtrado['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram:
        df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]

    # --- Interface Principal ---
    
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado encontrado com os filtros selecionados.")
    else:
        # KPIs Gerais
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador", f"{df_filtrado['atletas.pontos_num'].max()} pts")
        k2.metric("Média Geral", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
        k3.metric("Média de Preço", f"C$ {df_filtrado['atletas.preco_num'].mean():.2f}")
        k4.metric("Jogadores Analisados", f"{len(df_filtrado)}")

        st.markdown("---")

        # Abas
        tab_destaques, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🏆 Destaques (Jogadores)", 
            "🛡️ Análise de Times", 
            "📊 Scouts (Casa vs Fora)", 
            "💰 Valorização", 
            "📋 Tabela Completa"
        ])

        # --- ABA 1: DESTAQUES JOGADORES ---
        with tab_destaques:
            st.subheader("Líderes por Scout (Filtro Atual)")
            
            col_d1, col_d2, col_d3, col_d4 = st.columns(4)
            
            def get_top_player(coluna):
                if df_filtrado[coluna].sum() == 0: return "Ninguém", 0.0
                idx = df_filtrado[coluna].idxmax()
                row = df_filtrado.loc[idx]
                return f"{row['atletas.apelido']} ({row['atletas.clube.id.full.name']})", row[coluna]

            top_g_nome, top_g_val = get_top_player('G')
            top_a_nome, top_a_val = get_top_player('A')
            top_ds_nome, top_ds_val = get_top_player('DS')
            top_fin_nome, top_fin_val = get_top_player('finalizacoes_total')

            col_d1.metric("⚽ Artilheiro", top_g_nome, f"{int(top_g_val)} Gols")
            col_d2.metric("👟 Garçom (Assist)", top_a_nome, f"{int(top_a_val)} Assis.")
            col_d3.metric("🛑 Rei dos Desarmes", top_ds_nome, f"{int(top_ds_val)} DS")
            col_d4.metric("🚀 Mais Finaliza", top_fin_nome, f"{int(top_fin_val)} Finaliz.")

            st.divider()
            
            # Top 10 Geral Pontuação
            st.markdown("##### Top 10 Pontuadores")
            top10 = df_filtrado.nlargest(10, 'atletas.pontos_num')[['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.pontos_num', 'media_basica']]
            st.dataframe(top10, hide_index=True, use_container_width=True)

        # --- ABA 2: ANÁLISE DE TIMES ---
        with tab_times:
            st.subheader("Performance Agregada dos Clubes")
            
            # Agrupamento
            club_stats = df_filtrado.groupby('atletas.clube.id.full.name').agg({
                'atletas.pontos_num': ['mean', 'max', 'sum'],
                'finalizacoes_total': 'sum',
                'DS': 'sum',
                'SG': 'sum',
                'G': 'sum'
            }).reset_index()
            
            # Achatando colunas MultiIndex
            club_stats.columns = ['Clube', 'Media_Pontos', 'Max_Pontos', 'Soma_Pontos', 'Total_Finalizacoes', 'Total_Desarmes', 'Total_SG', 'Total_Gols']
            
            c_t1, c_t2 = st.columns(2)
            
            with c_t1:
                st.markdown("**Média de Pontos por Jogador (Eficiência)**")
                fig_times_pts = px.bar(club_stats.sort_values('Media_Pontos', ascending=False), 
                                       x='Media_Pontos', y='Clube', orientation='h',
                                       color='Media_Pontos', color_continuous_scale='Blues')
                st.plotly_chart(fig_times_pts, use_container_width=True)

            with c_t2:
                st.markdown("**Times que mais Finalizam (Volume Ofensivo)**")
                fig_times_fin = px.bar(club_stats.sort_values('Total_Finalizacoes', ascending=False), 
                                       x='Total_Finalizacoes', y='Clube', orientation='h',
                                       color='Total_Finalizacoes', color_continuous_scale='Reds')
                st.plotly_chart(fig_times_fin, use_container_width=True)

            c_t3, c_t4 = st.columns(2)
            with c_t3:
                st.markdown("**Segurança Defensiva (Soma de SG + Desarmes)**")
                club_stats['Indice_Defensivo'] = club_stats['Total_SG'] + club_stats['Total_Desarmes']
                fig_times_def = px.bar(club_stats.sort_values('Indice_Defensivo', ascending=False), 
                                       x='Indice_Defensivo', y='Clube', orientation='h',
                                       color='Indice_Defensivo', color_continuous_scale='Greens')
                st.plotly_chart(fig_times_def, use_container_width=True)
            
            with c_t4:
                st.markdown("**Tabela Resumo dos Times**")
                st.dataframe(club_stats.sort_values('Soma_Pontos', ascending=False), hide_index=True, use_container_width=True)

        # --- ABA 3: SCOUTS CASA VS FORA ---
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

        # --- ABA 4: VALORIZAÇÃO ---
        with tab_valorizacao:
            st.subheader("Relação Preço x Entrega")
            fig_val = px.scatter(
                df_filtrado, 
                x='atletas.preco_num', 
                y='atletas.pontos_num',
                color='posicao_nome',
                size='tamanho_visual',
                hover_data=['atletas.apelido', 'atletas.clube.id.full.name', 'media_basica'],
                title="Quem entrega mais pontos por C$ investido? (Bolha = Média Básica)"
            )
            st.plotly_chart(fig_val, use_container_width=True)

        # --- ABA 5: TABELA COMPLETA ---
        with tab_tabela:
            st.subheader("Dados Detalhados")
            cols_view = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'Mando_Padrao', 
                         'atletas.preco_num', 'atletas.pontos_num', 'media_basica', 
                         'G', 'A', 'DS', 'finalizacoes_total']
            
            cols_existentes = [c for c in cols_view if c in df_filtrado.columns]
            
            st.dataframe(
                df_filtrado[cols_existentes].sort_values('atletas.pontos_num', ascending=False),
                use_container_width=True,
                hide_index=True
            )

else:
    st.info("Aguardando carregamento dos dados...")
