import streamlit as st
import pandas as pd
import glob
import plotly.express as px

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

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
            # Cria a coluna de Mando Padrão
            temp_df['Mando_Padrao'] = temp_df['Mando'].apply(
                lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA'
            )
            df_jogos_list.append(temp_df)
        except Exception as e:
            pass
            
    df_jogos = pd.concat(df_jogos_list, ignore_index=True) if df_jogos_list else pd.DataFrame()
    
    return df_main, df_jogos

# --- Função para tratar URL da Foto ---
def formatar_foto(url):
    if pd.isna(url) or str(url) == 'nan':
        return "https://via.placeholder.com/220?text=Sem+Foto"
    # A API do Cartola retorna "FORMATO", precisamos substituir pelo tamanho
    return str(url).replace('FORMATO', '220x220')

# Executa o carregamento
df, df_jogos = load_data()

# --- Processamento ---
if df.empty:
    st.error("⚠️ Nenhum dado encontrado. Verifique os arquivos CSV.")
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

    # Mapeamentos
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # --- GARANTIA DE SCOUTS (Preenche com 0 se não existir) ---
    # Lista completa solicitada
    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'I', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'CA', 'CV', 'GC', 'PP']
    
    for col in todos_scouts:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- CÁLCULO CORRIGIDO DA MÉDIA BÁSICA ---
    # Média Básica = Pontos Totais - Pontos de Scouts Principais (Gols, Assist, SG, Defesa Penalti)
    # G=8, A=5, SG=5, DP=7
    df['media_basica'] = df['atletas.pontos_num'] - (8 * df['G']) - (5 * df['A']) - (5 * df['SG']) - (7 * df['DP'])
    
    # Cálculos auxiliares
    df['tamanho_visual'] = df['media_basica'].apply(lambda x: max(0.1, x))
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR (FILTROS) ---
    # ==========================================
    st.sidebar.header("🔍 Filtros")
    
    # Rodada
    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    sel_rodada_range = st.sidebar.slider("Rodada", min_rodada, max_rodada, (min_rodada, max_rodada))

    # Preço e Pontos
    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Preço (C$)", min_preco, max_preco, (min_preco, max_preco))
    
    # Filtros Categóricos
    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    all_posicoes = sorted(df['posicao_nome'].dropna().unique())

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    somente_jogaram = st.sidebar.checkbox("Apenas quem jogou?", value=True)

    # Aplicação
    df_filtrado = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1]) &
        (df['atletas.preco_num'] >= sel_preco_range[0]) &
        (df['atletas.preco_num'] <= sel_preco_range[1])
    ]
    
    if sel_clube: df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if somente_jogaram: df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]

    # ==========================================
    # --- DASHBOARD ---
    # ==========================================
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado encontrado com os filtros selecionados.")
    else:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador", f"{df_filtrado['atletas.pontos_num'].max():.1f}")
        k2.metric("Média Geral", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
        k3.metric("Média Básica (S/ Gols)", f"{df_filtrado['media_basica'].mean():.2f}")
        k4.metric("Jogadores", f"{len(df_filtrado)}")

        st.markdown("---")
        
        tab_destaques, tab_times, tab_valorizacao, tab_tabela = st.tabs([
            "🏆 Destaques por Scout", 
            "🛡️ Times", 
            "💎 Valorização", 
            "📋 Tabela Completa"
        ])

        # --- ABA 1: DESTAQUES (REFORMULADA COM FOTOS) ---
        with tab_destaques:
            st.markdown("#### 🔥 Líderes de Estatísticas")
            
            # Função para renderizar o cartão do jogador
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
                    with c_img:
                        st.image(foto_url, width=80)
                    with c_info:
                        st.caption(f"{row['atletas.apelido']}")
                        st.caption(f"{row['atletas.clube.id.full.name']}")
                        st.metric("Total", int(row[col_scout]))
                    st.divider()

            # Grupo 1: Ataque
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
            c8.empty() # Espaço vazio para alinhar

            # Grupo 2: Defesa
            st.info("🛡️ **Setor Defensivo**")
            d1, d2, d3, d4 = st.columns(4)
            render_destaque("Desarmes (DS)", 'DS', d1)
            render_destaque("Saldo de Gol (SG)", 'SG', d2)
            render_destaque("Defesas (DE)", 'DE', d3)
            render_destaque("Pênaltis Def (DP)", 'DP', d4)

            # Grupo 3: Negativos/Disciplina
            st.warning("⚠️ **Disciplina e Erros**")
            n1, n2, n3, n4 = st.columns(4)
            render_destaque("Gols Sofridos (GS)", 'GS', n1)
            render_destaque("Faltas Cometidas (FC)", 'FC', n2)
            render_destaque("Cartão Amarelo (CA)", 'CA', n3)
            render_destaque("Cartão Vermelho (CV)", 'CV', n4)
            
            n5, n6, n7, n8 = st.columns(4)
            render_destaque("Gol Contra (GC)", 'GC', n5)
            render_destaque("Pênalti Perdido (PP)", 'PP', n6)

        # --- ABA 2: TIMES ---
        with tab_times:
            st.subheader("Performance por Clube")
            club_stats = df_filtrado.groupby('atletas.clube.id.full.name').agg({
                'atletas.pontos_num': 'mean',
                'finalizacoes_total': 'sum',
                'DS': 'sum',
                'SG': 'sum'
            }).reset_index()
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                fig_pts = px.bar(club_stats.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h', title="Média de Pontos")
                st.plotly_chart(fig_pts, use_container_width=True)
            with col_t2:
                fig_ds = px.bar(club_stats.sort_values('DS'), x='DS', y='atletas.clube.id.full.name', orientation='h', title="Total de Desarmes", color_discrete_sequence=['#2E8B57'])
                st.plotly_chart(fig_ds, use_container_width=True)

        # --- ABA 3: VALORIZAÇÃO ---
        with tab_valorizacao:
            st.subheader("Mapa de Custo-Benefício")
            fig_val = px.scatter(
                df_filtrado, 
                x='atletas.preco_num', 
                y='atletas.pontos_num',
                color='posicao_nome',
                size='tamanho_visual',
                hover_name='atletas.apelido',
                hover_data=['media_basica', 'atletas.clube.id.full.name'],
                title="Preço x Pontuação (Tamanho = Média Básica)"
            )
            # Linhas médias
            fig_val.add_hline(y=df_filtrado['atletas.pontos_num'].mean(), line_dash="dash", line_color="gray")
            fig_val.add_vline(x=df_filtrado['atletas.preco_num'].mean(), line_dash="dash", line_color="gray")
            st.plotly_chart(fig_val, use_container_width=True)

        # --- ABA 4: TABELA ---
        with tab_tabela:
            st.subheader("Dados Brutos")
            cols_view = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.pontos_num', 'media_basica', 'G', 'A', 'DS', 'SG', 'DE', 'FS', 'FF', 'FD', 'FT', 'CA', 'CV']
            st.dataframe(df_filtrado[cols_view].sort_values('atletas.pontos_num', ascending=False), hide_index=True, use_container_width=True)
