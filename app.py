import streamlit as st
import pandas as pd
import glob
import plotly.express as px
import plotly.graph_objects as go

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide", initial_sidebar_state="expanded")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

# --- Estilo CSS para melhorar abas ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.2rem;
        font-weight: bold;
    }
    .stDataFrame { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- Funções Auxiliares ---
def formatar_foto(url):
    if pd.isna(url) or str(url) == 'nan':
        return "https://via.placeholder.com/220?text=Sem+Foto"
    return str(url).replace('FORMATO', '220x220')

# --- Funções de Carregamento ---
@st.cache_data
def load_data():
    # 1. Carregar Rodadas
    rodada_files = sorted(glob.glob("rodada-*.csv"))
    if not rodada_files: return pd.DataFrame(), pd.DataFrame()
    
    dfs = []
    for f in rodada_files:
        try:
            temp = pd.read_csv(f)
            temp.columns = temp.columns.str.strip()
            dfs.append(temp)
        except: pass
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    if not df_main.empty: df_main = df_main.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    # 2. Carregar Confrontos
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos_list = []
    for f in confronto_files:
        try:
            temp_df = pd.read_csv(f)
            temp_df.columns = temp_df.columns.str.strip()
            if 'Mando' in temp_df.columns:
                temp_df['Mando_Padrao'] = temp_df['Mando'].apply(lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA')
            else: temp_df['Mando_Padrao'] = 'N/A'
            df_jogos_list.append(temp_df)
        except: pass
            
    df_jogos = pd.concat(df_jogos_list, ignore_index=True) if df_jogos_list else pd.DataFrame()
    if not df_jogos.empty: df_jogos = df_jogos.drop_duplicates(subset=['rodada_id', 'clube_id'])
    
    return df_main, df_jogos

df, df_jogos = load_data()

# --- Processamento ---
if df.empty:
    st.error("⚠️ Nenhum dado encontrado.")
else:
    # Tipagem e Limpeza
    df['atletas.rodada_id'] = pd.to_numeric(df['atletas.rodada_id'], errors='coerce').fillna(0).astype(int)
    df['atletas.clube_id'] = pd.to_numeric(df['atletas.clube_id'], errors='coerce').fillna(0).astype(int)
    
    if not df_jogos.empty:
        df_jogos['rodada_id'] = pd.to_numeric(df_jogos['rodada_id'], errors='coerce').fillna(0).astype(int)
        df_jogos['clube_id'] = pd.to_numeric(df_jogos['clube_id'], errors='coerce').fillna(0).astype(int)
        
        cols_jogo = ['rodada_id', 'clube_id']
        for c in ['Mando_Padrao', 'Adversario', 'Estadio', 'Data', 'Hora']:
            if c in df_jogos.columns: cols_jogo.append(c)

        df = pd.merge(df, df_jogos[cols_jogo], left_on=['atletas.rodada_id', 'atletas.clube_id'], right_on=['rodada_id', 'clube_id'], how='left')
    
    for c in ['Mando_Padrao', 'Adversario']:
        if c not in df.columns: df[c] = 'N/A'
        df[c] = df[c].fillna('N/A')

    df = df.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])
    
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns: df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Auxiliares
    df['tamanho_visual'] = df['atletas.pontos_num'].apply(lambda x: max(1.0, x))
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR (Filtros Globais) ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Globais")
    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    sel_rodada_range = st.sidebar.slider("Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))
    
    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Preço (C$)", min_preco, max_preco, (min_preco, max_preco))
    
    st.sidebar.markdown("---")
    
    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", sorted(df['posicao_nome'].dropna().unique()), default=sorted(df['posicao_nome'].dropna().unique()))
    sel_mando = st.sidebar.multiselect("Mando", ['CASA', 'FORA'], default=['CASA', 'FORA'])
    
    # --- FILTRAGEM ---
    df_filtrado_base = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) & (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]
    if sel_clube: df_filtrado_base = df_filtrado_base[df_filtrado_base['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_filtrado_base = df_filtrado_base[df_filtrado_base['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_filtrado_base = df_filtrado_base[df_filtrado_base['Mando_Padrao'].isin(sel_mando)]
    
    df_filtrado_completo = df_filtrado_base[
        (df_filtrado_base['atletas.preco_num'] >= sel_preco_range[0]) & (df_filtrado_base['atletas.preco_num'] <= sel_preco_range[1])
    ]

    # --- AGRUPAMENTO ---
    def agrupar_dados(dataframe_input):
        if dataframe_input.empty: return pd.DataFrame()
        df_sorted = dataframe_input.sort_values('atletas.rodada_id', ascending=True)
        
        agg_dict = {
            'atletas.pontos_num': 'sum',
            'atletas.preco_num': 'last', 'atletas.apelido': 'last',
            'atletas.clube.id.full.name': 'last', 'atletas.clube_id': 'last',
            'posicao_nome': 'last', 'atletas.foto': 'last',
            'finalizacoes_total': 'last', 'atletas.jogos_num': 'last'
        }
        for s in todos_scouts: agg_dict[s] = 'last'
            
        df_grouped = df_sorted.groupby('atletas.atleta_id').agg(agg_dict).reset_index()
        df_grouped.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)
        return df_grouped

    df_agrupado_geral = agrupar_dados(df_filtrado_completo)
    df_pool_total = agrupar_dados(df_filtrado_base)

    # ==========================================
    # --- DASHBOARD (ABAS AGRUPADAS) ---
    # ==========================================
    if df_agrupado_geral.empty and df_pool_total.empty:
        st.warning("⚠️ Nenhum jogador encontrado.")
    else:
        # ABAS PRINCIPAIS (Para resolver visibilidade)
        tab_principal_1, tab_principal_2, tab_principal_3, tab_principal_4 = st.tabs([
            "📅 Central de Jogos", 
            "🤖 Inteligência & Robô", 
            "📊 Análise Tática", 
            "📈 Mercado & Dados"
        ])

        # ---------------------------------------------------------
        # ABA 1: CENTRAL DE JOGOS (Compacta)
        # ---------------------------------------------------------
        with tab_principal_1:
            if not df_jogos.empty:
                col_sel, col_kpi = st.columns([1, 3])
                with col_sel:
                    rodadas_disp = sorted(df_jogos['rodada_id'].unique())
                    rodada_selecionada = st.selectbox("Selecione a Rodada:", rodadas_disp)
                
                # Dados da rodada
                jogos_r = df_jogos[df_jogos['rodada_id'] == rodada_selecionada]
                stats_clubes = df.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])['atletas.pontos_num'].mean().reset_index()
                
                # Filtrar Mandantes
                jogos_unicos = jogos_r[jogos_r['Mando_Padrao'] == 'CASA'].copy()
                
                if not jogos_unicos.empty:
                    # Preparar Dados para Tabela Compacta
                    tabela_jogos = []
                    mapa_nomes = df[['atletas.clube_id', 'atletas.clube.id.full.name']].drop_duplicates().set_index('atletas.clube_id')['atletas.clube.id.full.name'].to_dict()

                    for _, jogo in jogos_unicos.iterrows():
                        mandante = mapa_nomes.get(jogo['clube_id'], f"ID {jogo['clube_id']}")
                        visitante = jogo['Adversario']
                        
                        # Buscar Médias
                        media_mandante = stats_clubes[(stats_clubes['atletas.clube.id.full.name'] == mandante) & (stats_clubes['Mando_Padrao'] == 'CASA')]['atletas.pontos_num'].mean()
                        media_visitante = stats_clubes[(stats_clubes['atletas.clube.id.full.name'] == visitante) & (stats_clubes['Mando_Padrao'] == 'FORA')]['atletas.pontos_num'].mean()
                        
                        # Alerta de Fragilidade Defensiva (Exemplo simples)
                        alerta = ""
                        if media_mandante < 40: alerta += f"⚠️ {mandante} mal em casa "
                        if media_visitante < 30: alerta += f"⚠️ {visitante} mal fora"

                        tabela_jogos.append({
                            "Data/Hora": f"{jogo.get('Data','')} {jogo.get('Hora','')}",
                            "Mandante": mandante,
                            "Força (Casa)": media_mandante if pd.notna(media_mandante) else 0,
                            "Visitante": visitante,
                            "Força (Fora)": media_visitante if pd.notna(media_visitante) else 0,
                            "Local": jogo.get('Estadio', ''),
                            "Obs": alerta
                        })
                    
                    df_tabela_jogos = pd.DataFrame(tabela_jogos)
                    
                    st.dataframe(
                        df_tabela_jogos,
                        column_config={
                            "Força (Casa)": st.column_config.ProgressColumn("Média Pts (Casa)", format="%.1f", min_value=0, max_value=100),
                            "Força (Fora)": st.column_config.ProgressColumn("Média Pts (Fora)", format="%.1f", min_value=0, max_value=100),
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Sem jogos cadastrados como mandante.")
            else:
                st.warning("Carregue o arquivo de confrontos.")

            st.divider()
            
            # Destaques Rápidos
            st.subheader("🔥 Top 3 da Rodada (Geral)")
            cols = ['atletas.apelido', 'atletas.clube.id.full.name', 'pontuacao_total_periodo']
            st.dataframe(df_agrupado_geral.nlargest(3, 'pontuacao_total_periodo')[cols], use_container_width=True, hide_index=True)

        # ---------------------------------------------------------
        # ABA 2: INTELIGÊNCIA (Robô, Comparador, Capitão)
        # ---------------------------------------------------------
        with tab_principal_2:
            subtab_robo, subtab_comp, subtab_cap = st.tabs(["🤖 Robô Escalador", "⚔️ Comparador", "© Capitão"])
            
            # --- ROBÔ ---
            with subtab_robo:
                c1, c2 = st.columns(2)
                orcamento = c1.number_input("💰 Orçamento (C$)", value=100.0)
                esquema = c2.selectbox("Formação", ["4-3-3", "3-4-3", "3-5-2", "4-4-2", "5-3-2"])
                
                if st.button("🚀 Escalar Time"):
                    esquemas = {"4-3-3": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 3, 'Atacante': 3, 'Técnico': 0}, "3-4-3": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 3, 'Técnico': 0}, "3-5-2": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 5, 'Atacante': 2, 'Técnico': 0}, "4-4-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 4, 'Atacante': 2, 'Técnico': 0}, "5-3-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 3, 'Atacante': 2, 'Técnico': 0}}
                    
                    pool = df_pool_total.sort_values('pontuacao_total_periodo', ascending=False)
                    time_atual = []
                    for pos, qtd in esquemas[esquema].items():
                        if qtd > 0:
                            time_atual.append(pool[pool['posicao_nome'] == pos].head(qtd))
                    
                    if time_atual:
                        df_time = pd.concat(time_atual)
                        custo = df_time['atletas.preco_num'].sum()
                        
                        loop = 0
                        while custo > orcamento and loop < 100:
                            melhor_troca = None
                            melhor_ratio = float('inf')
                            for idx, sair in df_time.iterrows():
                                cands = pool[(pool['posicao_nome'] == sair['posicao_nome']) & (pool['atletas.preco_num'] < sair['atletas.preco_num']) & (~pool['atletas.atleta_id'].isin(df_time['atletas.atleta_id']))]
                                if not cands.empty:
                                    entrar = cands.iloc[0]
                                    econ = sair['atletas.preco_num'] - entrar['atletas.preco_num']
                                    if econ > 0:
                                        ratio = (sair['pontuacao_total_periodo'] - entrar['pontuacao_total_periodo']) / econ
                                        if ratio < melhor_ratio: melhor_ratio, melhor_troca = ratio, (idx, entrar)
                            if melhor_troca:
                                df_time = df_time.drop(melhor_troca[0])
                                df_time = pd.concat([df_time, melhor_troca[1].to_frame().T])
                                custo = df_time['atletas.preco_num'].sum()
                            else: break
                            loop += 1
                        
                        st.success(f"✅ Time Escalado! Custo: C$ {custo:.2f}")
                        
                        cols = st.columns(5)
                        i = 0
                        df_time['ordem'] = df_time['posicao_nome'].map({'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 5})
                        for _, row in df_time.sort_values('ordem').iterrows():
                            with cols[i % 5]:
                                st.image(formatar_foto(row.get('atletas.foto', '')), width=80)
                                st.caption(f"{row['posicao_nome']} | {row['atletas.apelido']}")
                                st.write(f"**{row['pontuacao_total_periodo']:.1f} pts**")
                                st.divider()
                            i += 1
                    else: st.warning("Dados insuficientes.")

            # --- COMPARADOR ---
            with subtab_comp:
                c1, c2 = st.columns(2)
                b1 = c1.text_input("Filtrar Jogador 1", "").strip().lower()
                b2 = c2.text_input("Filtrar Jogador 2", "").strip().lower()
                nomes = sorted(df_pool_total['atletas.apelido'].unique())
                l1 = [n for n in nomes if b1 in n.lower()] if b1 else nomes
                l2 = [n for n in nomes if b2 in n.lower()] if b2 else nomes
                
                p1_n = c1.selectbox("Jogador 1", l1, index=0 if l1 else None)
                p2_n = c2.selectbox("Jogador 2", l2, index=min(1, len(l2)-1) if l2 else None)
                
                if p1_n and p2_n:
                    d1 = df_pool_total[df_pool_total['atletas.apelido'] == p1_n].iloc[0]
                    d2 = df_pool_total[df_pool_total['atletas.apelido'] == p2_n].iloc[0]
                    cats = ['Pontos', 'Gols', 'Assist', 'Finalizações', 'Desarmes', 'Jogos']
                    jogos1 = d1['atletas.jogos_num'] if 'atletas.jogos_num' in d1 else 0
                    jogos2 = d2['atletas.jogos_num'] if 'atletas.jogos_num' in d2 else 0
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatterpolar(r=[d1['pontuacao_total_periodo'], d1['G'], d1['A'], d1['finalizacoes_total'], d1['DS'], jogos1], theta=cats, fill='toself', name=p1_n))
                    fig.add_trace(go.Scatterpolar(r=[d2['pontuacao_total_periodo'], d2['G'], d2['A'], d2['finalizacoes_total'], d2['DS'], jogos2], theta=cats, fill='toself', name=p2_n))
                    st.plotly_chart(fig, use_container_width=True)

            # --- CAPITÃO ---
            with subtab_cap:
                busca_cap = st.text_input("Buscar Capitão", "").strip().lower()
                if not df_jogos.empty:
                    rodada = st.selectbox("Simular Rodada (Capitão):", sorted(df_jogos['rodada_id'].unique()))
                    df_heat = df_filtrado_completo[df_filtrado_completo['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                    jogos = df_jogos[df_jogos['rodada_id'] == rodada][['clube_id', 'Adversario']]
                    
                    if not df_pool_total.empty:
                        df_cap = pd.merge(df_pool_total, jogos, left_on='atletas.clube_id', right_on='clube_id', how='inner')
                        if not df_cap.empty:
                            df_final = pd.merge(df_cap, df_heat, on=['Adversario', 'posicao_nome'], how='left')
                            df_final['media_cedida_adv'] = df_final['atletas.pontos_num'].fillna(0)
                            df_final['Score Capitão'] = df_final['pontuacao_total_periodo'] + (df_final['media_cedida_adv'] * 2)
                            
                            if busca_cap: df_final = df_final[df_final['atletas.apelido'].str.lower().str.contains(busca_cap)]
                            st.dataframe(df_final[['atletas.apelido', 'posicao_nome', 'Adversario', 'pontuacao_total_periodo', 'media_cedida_adv', 'Score Capitão']].sort_values('Score Capitão', ascending=False), use_container_width=True, hide_index=True)

        # ---------------------------------------------------------
        # ABA 3: TÁTICA (Raio-X, Times)
        # ---------------------------------------------------------
        with tab_principal_3:
            subtab_raio, subtab_times, subtab_casa = st.tabs(["🔥 Raio-X Adversário", "🛡️ Times", "🏠 Casa vs Fora"])
            
            with subtab_raio:
                if 'Adversario' in df_filtrado_completo.columns:
                    df_heat = df_filtrado_completo[df_filtrado_completo['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                    if not df_heat.empty:
                        pivot = df_heat.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                        st.plotly_chart(px.imshow(pivot, text_auto=".1f", color_continuous_scale="Reds", title="Média de Pontos Cedidos"), use_container_width=True)
            
            with subtab_times:
                g = df_filtrado_completo.groupby('atletas.clube.id.full.name')[['atletas.pontos_num', 'finalizacoes_total']].mean().reset_index()
                st.plotly_chart(px.bar(g.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h', title="Média Pontos"), use_container_width=True)

            with subtab_casa:
                if 'Mando_Padrao' in df_filtrado_completo.columns:
                    g = df_filtrado_completo.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total']].mean().reset_index()
                    st.plotly_chart(px.bar(g, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group', title="Ataque: Casa vs Fora"), use_container_width=True)

        # ---------------------------------------------------------
        # ABA 4: MERCADO & DADOS
        # ---------------------------------------------------------
        with tab_principal_4:
            subtab_tabela, subtab_val, subtab_destaques = st.tabs(["📋 Tabela Completa", "💎 Valorização", "🏆 Destaques por Scout"])
            
            with subtab_tabela:
                busca_tab = st.text_input("Buscar na Tabela", "").strip().lower()
                df_show = df_agrupado_geral
                if busca_tab: df_show = df_show[df_show['atletas.apelido'].str.lower().str.contains(busca_tab)]
                
                # SUGESTÃO DE ANÁLISE: Mínimo para Valorizar (Simplificado)
                # Fórmula aproximada: (Preço Atual * 0.45) - Média Anterior (Não temos média anterior exata aqui, então é estimativa)
                df_show['Min. Valorizar (Estimado)'] = (df_show['atletas.preco_num'] * 0.45) 
                
                cols = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.preco_num', 'Min. Valorizar (Estimado)', 'pontuacao_total_periodo'] + todos_scouts
                st.dataframe(df_show[cols].sort_values('pontuacao_total_periodo', ascending=False), use_container_width=True, hide_index=True)

            with subtab_val:
                st.plotly_chart(px.scatter(df_filtrado_completo, x='atletas.preco_num', y='atletas.pontos_num', color='posicao_nome', size='tamanho_visual', hover_name='atletas.apelido'), use_container_width=True)

            with subtab_destaques:
                # O layout antigo de Destaques que você gostava
                def render_d(l, c, cont):
                    if df_agrupado_geral.empty or c not in df_agrupado_geral or df_agrupado_geral[c].sum()==0: return
                    idx = df_agrupado_geral[c].idxmax()
                    r = df_agrupado_geral.loc[idx]
                    with cont:
                        st.markdown(f"**{l}**")
                        c1, c2 = st.columns([1,2])
                        c1.image(formatar_foto(r.get('atletas.foto','')), width=60)
                        c2.caption(f"{r['atletas.apelido']}")
                        st.metric("Total", int(r[c]))
                        st.divider()
                
                c1, c2, c3, c4 = st.columns(4)
                render_d("Gols", 'G', c1); render_d("Assist", 'A', c2); render_d("Trave", 'FT', c3); render_d("Fin. Def", 'FD', c4)
                c1, c2, c3, c4 = st.columns(4)
                render_d("Desarmes", 'DS', c1); render_d("SG", 'SG', c2); render_d("Defesas", 'DE', c3); render_d("Pen. Def", 'DP', c4)
