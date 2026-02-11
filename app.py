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
    rodada_files = glob.glob("rodada-*.csv")
    if not rodada_files:
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
    
    return df_main, df_jogos

# Executa o carregamento
df, df_jogos = load_data()

# --- Processamento ---
if df.empty:
    st.error("⚠️ Nenhum dado de rodada encontrado. Verifique se os arquivos 'rodada-*.csv' estão na pasta.")
else:
    # Tratamento de Tipos Seguros
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

    # Tratamento Entrou em Campo
    if 'atletas.entrou_em_campo' in df.columns:
        df['atletas.entrou_em_campo'] = df['atletas.entrou_em_campo'].astype(str).str.lower().isin(['true', '1', '1.0'])

    # Mapeamentos e Tratamentos de Posição
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # --- GARANTIA DE SCOUTS ---
    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- CÁLCULO DA MÉDIA BÁSICA ---
    df['media_basica'] = (
        (df['FT'] * 3.0) + 
        (df['FD'] * 1.2) + 
        (df['FF'] * 0.8) + 
        (df['FS'] * 0.5) + 
        (df['PS'] * 1.0) + 
        (df['DP'] * 7.0) + 
        (df['DE'] * 1.0) + 
        (df['DS'] * 1.2)
    )
    
    # Cálculos Auxiliares
    df['tamanho_visual'] = df['media_basica'].apply(lambda x: max(0.1, x))
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR: FILTROS ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Principais")

    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    sel_rodada_range = st.sidebar.slider("Intervalo de Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))

    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Faixa de Preço (C$)", min_preco, max_preco, (min_preco, max_preco))

    min_pts, max_pts = float(df['atletas.pontos_num'].min()), float(df['atletas.pontos_num'].max())
    sel_pts_range = st.sidebar.slider("Faixa de Pontuação", min_pts, max_pts, (min_pts, max_pts))
    
    st.sidebar.markdown("---")
    st.sidebar.header("📌 Filtros Categóricos")

    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    all_posicoes = sorted(df['posicao_nome'].dropna().unique())

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    
    opcoes_mando = ['CASA', 'FORA', 'N/A']
    sel_mando = st.sidebar.multiselect("Mando", opcoes_mando, default=['CASA', 'FORA'])
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # Aplicação
    df_filtrado = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1]) &
        (df['atletas.preco_num'] >= sel_preco_range[0]) &
        (df['atletas.preco_num'] <= sel_preco_range[1]) &
        (df['atletas.pontos_num'] >= sel_pts_range[0]) &
        (df['atletas.pontos_num'] <= sel_pts_range[1])
    ]
    
    if sel_clube: df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_filtrado = df_filtrado[df_filtrado['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram: df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]

    # ==========================================
    # --- INTERFACE PRINCIPAL ---
    # ==========================================
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum jogador atende a esses filtros. Tente ampliar as faixas na barra lateral.")
    else:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador", f"{df_filtrado['atletas.pontos_num'].max():.1f} pts")
        k2.metric("Média Geral", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
        k3.metric("Média Básica", f"{df_filtrado['media_basica'].mean():.2f}")
        k4.metric("Jogadores", f"{len(df_filtrado)}")

        st.markdown("---")

        # Novas Abas
        tab_destaques, tab_times, tab_adversarios, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🏆 Destaques", 
            "🛡️ Times", 
            "🔥 Raio-X Adversário", # <--- ABA NOVA AQUI
            "📊 Casa vs Fora", 
            "💎 Valorização", 
            "📋 Tabela Completa"
        ])

        # --- ABA 1: DESTAQUES ---
        with tab_destaques:
            st.markdown("#### 🔥 Líderes de Estatísticas")
            
            def render_destaque(label, col_scout, container):
                if df_filtrado[col_scout].sum() == 0:
                    container.info(f"{label}: 0")
                    return
                idx = df_filtrado[col_scout].idxmax()
                row = df_filtrado.loc[idx]
                foto_url = formatar_foto(row.get('atletas.foto', ''))
                with container:
                    st.markdown(f"**{label}**")
                    c_img, c_info = st.columns([1, 2])
                    with c_img: st.image(foto_url, width=80)
                    with c_info:
                        st.caption(f"{row['atletas.apelido']}")
                        st.caption(f"{row['atletas.clube.id.full.name']}")
                        st.metric("Total", int(row[col_scout]))
                    st.divider()

            st.success("⚽ **Setor Ofensivo**")
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

            st.info("🛡️ **Setor Defensivo**")
            d1, d2, d3, d4 = st.columns(4)
            render_destaque("Desarmes (DS)", 'DS', d1)
            render_destaque("Saldo de Gol (SG)", 'SG', d2)
            render_destaque("Defesas (DE)", 'DE', d3)
            render_destaque("Pênaltis Def (DP)", 'DP', d4)

            st.warning("⚠️ **Disciplina e Erros**")
            n1, n2, n3, n4 = st.columns(4)
            render_destaque("Gols Sofridos (GS)", 'GS', n1)
            render_destaque("Faltas Cometidas (FC)", 'FC', n2)
            render_destaque("Cartão Amarelo (CA)", 'CA', n3)
            render_destaque("Cartão Vermelho (CV)", 'CV', n4)
            n5, n6, n7, n8 = st.columns(4)
            render_destaque("Gol Contra (GC)", 'GC', n5)
            render_destaque("Pênalti Perdido (PP)", 'PP', n6)

        # --- ABA 2: TIMES (ANTIGA) ---
        with tab_times:
            club_stats = df_filtrado.groupby('atletas.clube.id.full.name').agg({
                'atletas.pontos_num': 'mean',
                'finalizacoes_total': 'sum',
                'DS': 'sum',
                'SG': 'sum'
            }).reset_index()
            c_t1, c_t2 = st.columns(2)
            with c_t1:
                st.subheader("Média de Pontos por Clube")
                st.plotly_chart(px.bar(club_stats.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h'), use_container_width=True)
            with c_t2:
                st.subheader("Volume Ofensivo (Finalizações)")
                st.plotly_chart(px.bar(club_stats.sort_values('finalizacoes_total'), x='finalizacoes_total', y='atletas.clube.id.full.name', orientation='h'), use_container_width=True)

        # --- ABA 3: RAIO-X ADVERSÁRIO (NOVA) ---
        with tab_adversarios:
            st.subheader("🔥 Mapa da Mina: Quem cede mais pontos?")
            st.markdown("Este gráfico mostra a **média de pontos cedidos** por cada time adversário para cada posição. **Quanto mais verde, melhor para escalar contra!**")
            
            if 'Adversario' in df_filtrado.columns and not df_filtrado['Adversario'].isin(['N/A']).all():
                # Preparar dados para o Heatmap
                heatmap_data = df_filtrado[df_filtrado['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                
                # Pivotar para formato de matriz
                heatmap_pivot = heatmap_data.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num')
                
                # Ordenar colunas logicamente
                order_pos = ['Goleiro', 'Zagueiro', 'Lateral', 'Meia', 'Atacante']
                heatmap_pivot = heatmap_pivot.reindex(columns=[p for p in order_pos if p in heatmap_pivot.columns])
                
                # Plotar Heatmap
                fig_heat = px.imshow(
                    heatmap_pivot,
                    labels=dict(x="Posição do seu Jogador", y="Adversário (Quem sofre)", color="Média Cedida"),
                    x=heatmap_pivot.columns,
                    y=heatmap_pivot.index,
                    text_auto='.1f',
                    color_continuous_scale='RdYlGn', # Vermelho (Ruim) -> Verde (Bom)
                    aspect="auto",
                    height=700
                )
                fig_heat.update_layout(title="Média de Pontos Cedidos pelo Adversário")
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.info("⚠️ Dados de confronto não disponíveis para gerar o mapa de calor. Verifique os arquivos 'confrontos_*.csv'.")

        # --- ABA 4: CASA VS FORA (ANTIGA) ---
        with tab_scouts:
            if not df_filtrado['Mando_Padrao'].isin(['N/A']).all():
                grupo_mando = df_filtrado.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group', title="Ataque (Casa vs Fora)"), use_container_width=True)
                with c2:
                    st.plotly_chart(px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_defensivos_total', color='Mando_Padrao', barmode='group', title="Defesa (Casa vs Fora)"), use_container_width=True)
            else:
                st.info("Filtre por CASA ou FORA para visualizar esta aba.")

        # --- ABA 5: VALORIZAÇÃO (ANTIGA) ---
        with tab_valorizacao:
            st.subheader("Relação Preço x Entrega")
            fig_val = px.scatter(
                df_filtrado, 
                x='atletas.preco_num', 
                y='atletas.pontos_num',
                color='posicao_nome',
                size='tamanho_visual',
                hover_name='atletas.apelido',
                title="Quem entrega mais pontos por C$ investido?"
            )
            st.plotly_chart(fig_val, use_container_width=True)

        # --- ABA 6: TABELA COMPLETA (MANTIDA) ---
        with tab_tabela:
            st.subheader("Buscador Detalhado de Scouts")
            cols_info = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'Mando_Padrao', 'Adversario', 'atletas.preco_num']
            cols_kpis = ['atletas.pontos_num', 'media_basica']
            cols_view = cols_info + cols_kpis + todos_scouts
            
            cols_existentes = [c for c in cols_view if c in df_filtrado.columns]
            df_display = df_filtrado[cols_existentes].sort_values('atletas.pontos_num', ascending=False)
            
            renomear = {
                'atletas.apelido': 'Apelido', 'atletas.clube.id.full.name': 'Clube',
                'posicao_nome': 'Posição', 'Mando_Padrao': 'Mando',
                'atletas.preco_num': 'Preço (C$)', 'atletas.pontos_num': 'Pontuação Total',
                'media_basica': 'Média Básica'
            }
            df_display = df_display.rename(columns=renomear)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
