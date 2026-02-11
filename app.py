import streamlit as st
import pandas as pd
import glob
import plotly.express as px

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

# --- Funções Auxiliares ---
def formatar_foto(url):
    """Corrige a URL da foto do jogador para o tamanho correto."""
    if pd.isna(url) or str(url) == 'nan':
        return "https://via.placeholder.com/220?text=Sem+Foto"
    return str(url).replace('FORMATO', '220x220')

# --- Funções de Carregamento ---
@st.cache_data
def load_data():
    # 1. Carregar dados das Rodadas
    rodada_files = sorted(glob.glob("rodada-*.csv"))
    if not rodada_files:
        return pd.DataFrame(), pd.DataFrame()
    
    dfs = []
    for f in rodada_files:
        try:
            temp = pd.read_csv(f)
            dfs.append(temp)
        except Exception as e:
            st.warning(f"Erro ao ler {f}: {e}")
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    # Remove duplicatas brutas
    if not df_main.empty:
        df_main = df_main.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    # 2. Carregar dados de Confrontos
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos_list = []
    
    for f in confronto_files:
        try:
            temp_df = pd.read_csv(f)
            temp_df['Mando_Padrao'] = temp_df['Mando'].apply(
                lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA'
            )
            df_jogos_list.append(temp_df)
        except Exception as e:
            pass
            
    df_jogos = pd.concat(df_jogos_list, ignore_index=True) if df_jogos_list else pd.DataFrame()
    if not df_jogos.empty:
        df_jogos = df_jogos.drop_duplicates(subset=['rodada_id', 'clube_id'])
    
    return df_main, df_jogos

# Executa o carregamento
df, df_jogos = load_data()

# --- Processamento ---
if df.empty:
    st.error("⚠️ Nenhum dado de rodada encontrado.")
else:
    # Tipagem Segura
    df['atletas.rodada_id'] = pd.to_numeric(df['atletas.rodada_id'], errors='coerce').fillna(0).astype(int)
    df['atletas.clube_id'] = pd.to_numeric(df['atletas.clube_id'], errors='coerce').fillna(0).astype(int)
    
    # Cruzamento com Jogos
    if not df_jogos.empty:
        df_jogos['rodada_id'] = pd.to_numeric(df_jogos['rodada_id'], errors='coerce').fillna(0).astype(int)
        df_jogos['clube_id'] = pd.to_numeric(df_jogos['clube_id'], errors='coerce').fillna(0).astype(int)

        df = pd.merge(
            df, 
            df_jogos[['rodada_id', 'clube_id', 'Mando_Padrao', 'Adversario']], 
            left_on=['atletas.rodada_id', 'atletas.clube_id'], 
            right_on=['rodada_id', 'clube_id'], 
            how='left'
        )
        df['Mando_Padrao'] = df['Mando_Padrao'].fillna('N/A')
        df['Adversario'] = df['Adversario'].fillna('N/A')
    else:
        df['Mando_Padrao'] = 'N/A'
        df['Adversario'] = 'N/A'

    # Remove duplicatas pós-merge
    df = df.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    # Entrou em Campo
    if 'atletas.entrou_em_campo' in df.columns:
        df['atletas.entrou_em_campo'] = df['atletas.entrou_em_campo'].astype(str).str.lower().isin(['true', '1', '1.0'])

    # Mapeamento Posição
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # Preenche Scouts com 0
    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Cálculo Média Básica (Por Linha/Rodada)
    df['media_basica'] = (
        (df['FT'] * 3.0) + (df['FD'] * 1.2) + (df['FF'] * 0.8) + 
        (df['FS'] * 0.5) + (df['PS'] * 1.0) + (df['DP'] * 7.0) + 
        (df['DE'] * 1.0) + (df['DS'] * 1.2)
    )
    
    # Proteção visual
    df['tamanho_visual'] = df['media_basica'].apply(lambda x: max(1.0, x) if pd.notnull(x) else 1.0)

    # Auxiliares
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR: FILTROS ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Principais")

    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    if min_rodada == max_rodada:
        sel_rodada_range = (min_rodada, max_rodada)
    else:
        sel_rodada_range = st.sidebar.slider("Intervalo de Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))

    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Faixa de Preço", min_preco, max_preco, (min_preco, max_preco))

    min_pts, max_pts = float(df['atletas.pontos_num'].min()), float(df['atletas.pontos_num'].max())
    sel_pts_range = st.sidebar.slider("Faixa de Pontuação (Por Jogo)", min_pts, max_pts, (min_pts, max_pts))
    
    st.sidebar.markdown("---")

    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    all_posicoes = sorted(df['posicao_nome'].dropna().unique())

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    
    opcoes_mando = ['CASA', 'FORA', 'N/A']
    sel_mando = st.sidebar.multiselect("Mando", opcoes_mando, default=['CASA', 'FORA'])
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # 1. Filtra as rodadas selecionadas
    df_periodo = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]

    # 2. Aplica demais filtros
    if sel_clube: df_periodo = df_periodo[df_periodo['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_periodo = df_periodo[df_periodo['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_periodo = df_periodo[df_periodo['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram: df_periodo = df_periodo[df_periodo['atletas.entrou_em_campo'] == True]

    # Aplica filtro de preço/pontos
    df_periodo = df_periodo[
        (df_periodo['atletas.preco_num'] >= sel_preco_range[0]) &
        (df_periodo['atletas.preco_num'] <= sel_preco_range[1]) &
        (df_periodo['atletas.pontos_num'] >= sel_pts_range[0]) &
        (df_periodo['atletas.pontos_num'] <= sel_pts_range[1])
    ]

    # ==========================================
    # --- AGRUPAMENTO INTELIGENTE (SNAPSHOT + SOMA) ---
    # ==========================================
    if not df_periodo.empty:
        # A) SOMA da Pontuação
        df_pontos = df_periodo.groupby('atletas.atleta_id')['atletas.pontos_num'].sum().reset_index()
        df_pontos.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)
        
        # B) SNAPSHOT dos Scouts (Pega o acumulado da última rodada selecionada)
        df_snapshot = df_periodo.sort_values('atletas.rodada_id', ascending=False).drop_duplicates('atletas.atleta_id')
        
        # Merge
        df_agrupado = pd.merge(df_snapshot, df_pontos, on='atletas.atleta_id', how='left')
        
        # Recalcula Média Básica (Soma acumulada pois vem do snapshot)
        df_agrupado['media_basica_total'] = (
            (df_agrupado['FT'] * 3.0) + (df_agrupado['FD'] * 1.2) + (df_agrupado['FF'] * 0.8) + 
            (df_agrupado['FS'] * 0.5) + (df_agrupado['PS'] * 1.0) + (df_agrupado['DP'] * 7.0) + 
            (df_agrupado['DE'] * 1.0) + (df_agrupado['DS'] * 1.2)
        )
    else:
        df_agrupado = pd.DataFrame()

    # ==========================================
    # --- INTERFACE ---
    # ==========================================
    if df_agrupado.empty:
        st.warning("⚠️ Nenhum jogador encontrado.")
    else:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador (Soma)", f"{df_agrupado['pontuacao_total_periodo'].max():.1f}")
        k2.metric("Média Geral (Por Jogo)", f"{df_periodo['atletas.pontos_num'].mean():.2f}")
        k3.metric("Pontuação Básica (Acumulada)", f"{df_agrupado['media_basica_total'].mean():.2f}")
        k4.metric("Jogadores", f"{len(df_agrupado)}")

        st.markdown("---")

        tab_destaques, tab_adversario, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🏆 Destaques", 
            "🛡️ Raio-X Adversário",
            "📊 Times", 
            "🏠 Casa vs Fora", 
            "💎 Valorização", 
            "📋 Tabela"
        ])

        # --- ABA 1: DESTAQUES ---
        with tab_destaques:
            st.markdown(f"#### 🔥 Líderes (Acumulado até a última rodada selecionada)")
            
            def render_destaque(label, col_scout, container):
                if df_agrupado[col_scout].sum() == 0:
                    container.info(f"{label}: 0")
                    return
                
                idx = df_agrupado[col_scout].idxmax()
                row = df_agrupado.loc[idx]
                foto_url = formatar_foto(row.get('atletas.foto', ''))
                
                with container:
                    st.markdown(f"**{label}**")
                    c_img, c_info = st.columns([1, 2])
                    with c_img:
                        st.image(foto_url, width=80)
                    with c_info:
                        st.caption(f"{row['atletas.apelido']}")
                        st.caption(f"{row['atletas.clube.id.full.name']}")
                        st.metric("Total", int(row[col_scout]))
                    st.divider()

            c1, c2, c3, c4 = st.columns(4)
            render_destaque("Artilheiro (G)", 'G', c1)
            render_destaque("Garçom (A)", 'A', c2)
            render_destaque("Fin. Trave (FT)", 'FT', c3)
            render_destaque("Fin. Defendida (FD)", 'FD', c4)
            
            c5, c6, c7, c8 = st.columns(4)
            render_destaque("Fin. Fora (FF)", 'FF', c5)
            render_destaque("Faltas Sofridas (FS)", 'FS', c6)
            render_destaque("Impedimentos (I)", 'I', c7)
            c8.empty() 

            d1, d2, d3, d4 = st.columns(4)
            render_destaque("Desarmes (DS)", 'DS', d1)
            render_destaque("Saldo de Gol (SG)", 'SG', d2)
            render_destaque("Defesas (DE)", 'DE', d3)
            render_destaque("Pênaltis Def (DP)", 'DP', d4)

            n1, n2, n3, n4 = st.columns(4)
            render_destaque("Gols Sofridos (GS)", 'GS', n1)
            render_destaque("Faltas Cometidas (FC)", 'FC', n2)
            render_destaque("Cartão Amarelo (CA)", 'CA', n3)
            render_destaque("Cartão Vermelho (CV)", 'CV', n4)

        # --- ABA 2: RAIO-X ADVERSÁRIO (REDESENHADA) ---
        with tab_adversario:
            st.subheader("🔥 Raio-X: Quem cede mais pontos por posição?")
            st.info("Quanto mais intensa a cor, mais pontos esse time costuma ceder para a posição específica.")
            
            if 'Adversario' in df_periodo.columns and not df_periodo['Adversario'].isin(['N/A']).all():
                # Prepara dados gerais
                df_heat = df_periodo[df_periodo['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                
                # Função para criar Heatmap específico
                def criar_heatmap_posicao(posicoes_alvo, titulo, cor_escala):
                    df_pos = df_heat[df_heat['posicao_nome'].isin(posicoes_alvo)]
                    if df_pos.empty: return None
                    
                    pivot = df_pos.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                    pivot['Total'] = pivot.sum(axis=1)
                    pivot = pivot.sort_values('Total', ascending=True).drop(columns='Total')
                    
                    fig = px.imshow(
                        pivot, 
                        text_auto=".1f", 
                        aspect="auto", 
                        color_continuous_scale=cor_escala,
                        title=titulo
                    )
                    fig.update_layout(height=600, xaxis_title=None, yaxis_title=None)
                    return fig

                # Layout em Colunas
                c_goleiro, c_defesa, c_meia, c_ataque = st.columns(4)

                with c_goleiro:
                    fig_gol = criar_heatmap_posicao(['Goleiro'], "🥅 Goleiros", "Blues")
                    if fig_gol: st.plotly_chart(fig_gol, use_container_width=True)

                with c_defesa:
                    fig_def = criar_heatmap_posicao(['Zagueiro', 'Lateral'], "🛡️ Defensores", "Greens")
                    if fig_def: st.plotly_chart(fig_def, use_container_width=True)

                with c_meia:
                    fig_mei = criar_heatmap_posicao(['Meia'], "🧠 Meias", "Oranges")
                    if fig_mei: st.plotly_chart(fig_mei, use_container_width=True)

                with c_ataque:
                    fig_ata = criar_heatmap_posicao(['Atacante'], "⚽ Atacantes", "Reds")
                    if fig_ata: st.plotly_chart(fig_ata, use_container_width=True)

            else:
                st.warning("Dados de Adversário indisponíveis.")

        # --- ABA 3: TIMES ---
        with tab_times:
            club_stats = df_periodo.groupby('atletas.clube.id.full.name').agg({
                'atletas.pontos_num': 'mean', 'finalizacoes_total': 'mean'
            }).reset_index()
            
            c_t1, c_t2 = st.columns(2)
            with c_t1:
                fig_pts = px.bar(club_stats.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h', title="Média de Pontos")
                st.plotly_chart(fig_pts, use_container_width=True)
            with c_t2:
                fig_fin = px.bar(club_stats.sort_values('finalizacoes_total'), x='finalizacoes_total', y='atletas.clube.id.full.name', orientation='h', title="Média Finalizações", color_discrete_sequence=['red'])
                st.plotly_chart(fig_fin, use_container_width=True)

        # --- ABA 4: CASA VS FORA ---
        with tab_scouts:
            if not df_periodo['Mando_Padrao'].isin(['N/A']).all():
                grupo_mando = df_periodo.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                c1, c2 = st.columns(2)
                with c1:
                    fig_of = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group', title="Média Scouts Ofensivos")
                    st.plotly_chart(fig_of, use_container_width=True)
                with c2:
                    fig_def = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_defensivos_total', color='Mando_Padrao', barmode='group', title="Média Scouts Defensivos")
                    st.plotly_chart(fig_def, use_container_width=True)
            else:
                st.info("Filtre por CASA ou FORA.")

        # --- ABA 5: VALORIZAÇÃO ---
        with tab_valorizacao:
            st.subheader("Relação Preço x Entrega (Jogo a Jogo)")
            fig_val = px.scatter(
                df_periodo, 
                x='atletas.preco_num', 
                y='atletas.pontos_num',
                color='posicao_nome',
                size='tamanho_visual',
                hover_name='atletas.apelido',
                hover_data=['media_basica', 'atletas.clube.id.full.name'],
                title="Preço x Pontuação (Bolha = Média Básica)"
            )
            st.plotly_chart(fig_val, use_container_width=True)

        # --- ABA 6: TABELA COMPLETA ---
        with tab_tabela:
            st.subheader("Tabela Consolidada")
            cols_info = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.preco_num']
            cols_kpis = ['pontuacao_total_periodo', 'media_basica_total']
            cols_view = cols_info + cols_kpis + todos_scouts
            
            df_display = df_agrupado[cols_view].sort_values('pontuacao_total_periodo', ascending=False)
            
            renomear = {
                'atletas.apelido': 'Apelido',
                'atletas.clube.id.full.name': 'Clube',
                'posicao_nome': 'Posição',
                'atletas.preco_num': 'Preço Atual (C$)',
                'pontuacao_total_periodo': 'Pontos Totais (Soma)',
                'media_basica_total': 'Pontuação Básica (Acumulada)'
            }
            
            df_display = df_display.rename(columns=renomear)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
