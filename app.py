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
    # 1. Carregar dados das Rodadas (Lê todos os CSVs disponíveis)
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

    # 2. Carregar dados de Confrontos (CORREÇÃO: Ler TODOS os arquivos, não apenas o [0])
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos_list = []
    
    for f in confronto_files:
        try:
            temp_df = pd.read_csv(f)
            # Cria a coluna de Mando Padrão já na leitura
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

# --- Processamento e Tratamento Seguros ---
if df.empty:
    st.error("⚠️ Nenhum dado de rodada encontrado. Verifique se os arquivos 'rodada-*.csv' estão na pasta.")
else:
    # Tratamento de Tipos Seguros (Evita quebrar se houver NaN)
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

    # Tratamento da coluna 'Entrou em Campo' (Garante que é Booleano)
    if 'atletas.entrou_em_campo' in df.columns:
        df['atletas.entrou_em_campo'] = df['atletas.entrou_em_campo'].astype(str).str.lower().isin(['true', '1', '1.0'])

    # Mapeamentos e Tratamentos de Posição
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # Preenchimento de Scouts Faltantes com 0
    scout_cols = ['G', 'A', 'DS', 'FC', 'FS', 'CA', 'FD', 'FF', 'FT', 'SG', 'DE', 'DP', 'GS']
    for col in scout_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Cálculos Avançados
    df['media_basica'] = df['atletas.pontos_num'] - (8 * df['G']) - (5 * df['A'])
    df['tamanho_visual'] = df['media_basica'].apply(lambda x: max(0.1, x)) # Proteção visual para o gráfico
    
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR: FILTROS E CONTROLES ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Principais")

    # 1. Filtro Deslizante de Rodada
    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    if min_rodada == max_rodada:
        sel_rodada_range = (min_rodada, max_rodada)
        st.sidebar.caption(f"Apenas dados da Rodada {min_rodada} disponíveis.")
    else:
        sel_rodada_range = st.sidebar.slider("Intervalo de Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))

    # 2. Filtro Deslizante de Preço e Pontuação
    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Faixa de Preço (C$)", min_preco, max_preco, (min_preco, max_preco))

    min_pts, max_pts = float(df['atletas.pontos_num'].min()), float(df['atletas.pontos_num'].max())
    sel_pts_range = st.sidebar.slider("Faixa de Pontuação", min_pts, max_pts, (min_pts, max_pts))
    
    st.sidebar.markdown("---")
    st.sidebar.header("📌 Filtros Categóricos")

    # CORREÇÃO: Usar 'default' preenchido garante que a tela não inicie vazia!
    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    all_posicoes = sorted(df['posicao_nome'].dropna().unique())

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    
    opcoes_mando = ['CASA', 'FORA', 'N/A']
    sel_mando = st.sidebar.multiselect("Mando", opcoes_mando, default=['CASA', 'FORA'])
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # ==========================================
    # --- APLICAÇÃO DOS FILTROS ---
    # ==========================================
    df_filtrado = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1]) &
        (df['atletas.preco_num'] >= sel_preco_range[0]) &
        (df['atletas.preco_num'] <= sel_preco_range[1]) &
        (df['atletas.pontos_num'] >= sel_pts_range[0]) &
        (df['atletas.pontos_num'] <= sel_pts_range[1])
    ]
    
    if sel_clube:
        df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao:
        df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if sel_mando:
        df_filtrado = df_filtrado[df_filtrado['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram:
        df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]

    # ==========================================
    # --- INTERFACE PRINCIPAL ---
    # ==========================================
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum jogador atende a esses filtros. Tente ampliar as faixas na barra lateral.")
    else:
        # KPIs Gerais
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador", f"{df_filtrado['atletas.pontos_num'].max():.1f} pts")
        k2.metric("Média Geral", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
        k3.metric("Média de Preço", f"C$ {df_filtrado['atletas.preco_num'].mean():.2f}")
        k4.metric("Jogadores Analisados", f"{len(df_filtrado)}")

        st.markdown("---")

        # Abas do Dashboard
        tab_destaques, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🏆 Destaques", 
            "🛡️ Análise de Times", 
            "📊 Casa vs Fora", 
            "💎 Mapa de Valorização", 
            "📋 Tabela Completa"
        ])

        # --- ABA 1: DESTAQUES ---
        with tab_destaques:
            col_d1, col_d2, col_d3, col_d4 = st.columns(4)
            
            def get_top_player(coluna):
                if df_filtrado[coluna].sum() == 0: return "Ninguém", 0.0
                idx = df_filtrado[coluna].idxmax()
                row = df_filtrado.loc[idx]
                return f"{row['atletas.apelido']} ({row['atletas.clube.id.full.name'][:3].upper()})", row[coluna]

            top_g_nome, top_g_val = get_top_player('G')
            top_a_nome, top_a_val = get_top_player('A')
            top_ds_nome, top_ds_val = get_top_player('DS')
            top_fin_nome, top_fin_val = get_top_player('finalizacoes_total')

            col_d1.metric("⚽ Artilheiro", top_g_nome, f"{int(top_g_val)} Gols")
            col_d2.metric("👟 Garçom (Assist)", top_a_nome, f"{int(top_a_val)} Assis.")
            col_d3.metric("🛑 Rei dos Desarmes", top_ds_nome, f"{int(top_ds_val)} DS")
            col_d4.metric("🚀 Mais Finaliza", top_fin_nome, f"{int(top_fin_val)} Finaliz.")

            st.markdown("##### Top 10 Pontuadores (Ranking de Eficiência)")
            top10 = df_filtrado.nlargest(10, 'atletas.pontos_num')[
                ['atletas.apelido', 'posicao_nome', 'atletas.clube.id.full.name', 'Mando_Padrao', 'Adversario', 'atletas.preco_num', 'atletas.pontos_num']
            ]
            st.dataframe(top10, hide_index=True, use_container_width=True)

        # --- ABA 2: ANÁLISE DE TIMES ---
        with tab_times:
            club_stats = df_filtrado.groupby('atletas.clube.id.full.name').agg({
                'atletas.pontos_num': 'mean',
                'finalizacoes_total': 'sum',
                'DS': 'sum',
                'SG': 'sum'
            }).reset_index()
            club_stats.columns = ['Clube', 'Media_Pontos', 'Total_Finalizacoes', 'Total_Desarmes', 'Total_SG']
            
            c_t1, c_t2 = st.columns(2)
            with c_t1:
                fig_pts = px.bar(club_stats.sort_values('Media_Pontos', ascending=True), 
                                 x='Media_Pontos', y='Clube', orientation='h',
                                 title="Média de Pontos por Clube",
                                 color='Media_Pontos', color_continuous_scale='Blues')
                st.plotly_chart(fig_pts, use_container_width=True)

            with c_t2:
                fig_fin = px.bar(club_stats.sort_values('Total_Finalizacoes', ascending=True), 
                                 x='Total_Finalizacoes', y='Clube', orientation='h',
                                 title="Volume Ofensivo (Finalizações)",
                                 color='Total_Finalizacoes', color_continuous_scale='Reds')
                st.plotly_chart(fig_fin, use_container_width=True)

        # --- ABA 3: CASA VS FORA ---
        with tab_scouts:
            if not df_filtrado['Mando_Padrao'].isin(['N/A']).all():
                grupo_mando = df_filtrado.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                
                c1, c2 = st.columns(2)
                with c1:
                    fig_of = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', 
                                    color='Mando_Padrao', barmode='group', title="Média de Scouts Ofensivos",
                                    color_discrete_map={'CASA': '#2E8B57', 'FORA': '#CD5C5C'})
                    st.plotly_chart(fig_of, use_container_width=True)
                
                with c2:
                    fig_def = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_defensivos_total', 
                                    color='Mando_Padrao', barmode='group', title="Média de Scouts Defensivos",
                                    color_discrete_map={'CASA': '#2E8B57', 'FORA': '#CD5C5C'})
                    st.plotly_chart(fig_def, use_container_width=True)
            else:
                st.info("Filtre por CASA ou FORA para visualizar esta aba.")

        # --- ABA 4: VALORIZAÇÃO (O GRÁFICO PREMIUM) ---
        with tab_valorizacao:
            st.markdown("### Mapa de Custo-Benefício (Preço x Entrega)")
            st.write("Identifique visualmente os jogadores que entregam muitos pontos custando pouco.")
            
            # Gráfico de Dispersão Avançado
            fig_val = px.scatter(
                df_filtrado, 
                x='atletas.preco_num', 
                y='atletas.pontos_num',
                color='posicao_nome',
                size='tamanho_visual',
                hover_name='atletas.apelido',
                hover_data={
                    'posicao_nome': True,
                    'atletas.clube.id.full.name': True,
                    'atletas.preco_num': ':.2f',
                    'atletas.pontos_num': ':.1f',
                    'media_basica': ':.1f',
                    'tamanho_visual': False # Esconde a variável técnica do hover
                },
                labels={
                    'atletas.preco_num': 'Preço Atual (C$)',
                    'atletas.pontos_num': 'Pontos na Rodada',
                    'posicao_nome': 'Posição'
                },
                template='plotly_white',
                height=600
            )

            # Adicionando Linhas de Quadrante (Médias)
            media_preco = df_filtrado['atletas.preco_num'].mean()
            media_pontos = df_filtrado['atletas.pontos_num'].mean()

            fig_val.add_hline(y=media_pontos, line_dash="dash", line_color="gray", annotation_text="Média de Pontos")
            fig_val.add_vline(x=media_preco, line_dash="dash", line_color="gray", annotation_text="Preço Médio")
            
            # Anotações Estratégicas nos quadrantes
            fig_val.add_annotation(x=media_preco/2, y=df_filtrado['atletas.pontos_num'].max(), text="💎 Zona de Ouro (Barato e Pontua Muito)", showarrow=False, font=dict(color="green", size=14))
            fig_val.add_annotation(x=df_filtrado['atletas.preco_num'].max(), y=df_filtrado['atletas.pontos_num'].min(), text="⛔ Zona de Risco (Caro e Pontua Pouco)", showarrow=False, font=dict(color="red", size=14))

            # Estilização
            fig_val.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')), opacity=0.8)
            st.plotly_chart(fig_val, use_container_width=True)

        # --- ABA 5: TABELA COMPLETA ---
        with tab_tabela:
            st.subheader("Buscador Detalhado")
            cols_view = [
                'atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 
                'Mando_Padrao', 'Adversario', 'atletas.preco_num', 'atletas.pontos_num', 
                'media_basica', 'G', 'A', 'DS', 'SG', 'finalizacoes_total'
            ]
            
            cols_existentes = [c for c in cols_view if c in df_filtrado.columns]
            
            # Renomear para ficar bonito na tabela
            df_display = df_filtrado[cols_existentes].sort_values('atletas.pontos_num', ascending=False)
            df_display.columns = [c.replace('atletas.', '').replace('.id.full.name', '').replace('_num', '').replace('_', ' ').title() for c in cols_existentes]
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
