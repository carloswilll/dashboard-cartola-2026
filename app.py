import streamlit as st
import pandas as pd
import glob
import plotly.express as px
import plotly.graph_objects as go

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

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
    if not rodada_files:
        return pd.DataFrame(), pd.DataFrame()
    
    dfs = []
    for f in rodada_files:
        try:
            temp = pd.read_csv(f)
            temp.columns = temp.columns.str.strip()
            dfs.append(temp)
        except Exception as e:
            st.warning(f"Erro ao ler {f}: {e}")
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    if not df_main.empty:
        df_main = df_main.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    # 2. Carregar Confrontos
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos_list = []
    
    for f in confronto_files:
        try:
            temp_df = pd.read_csv(f)
            temp_df.columns = temp_df.columns.str.strip()
            if 'Mando' in temp_df.columns:
                temp_df['Mando_Padrao'] = temp_df['Mando'].apply(
                    lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA'
                )
            else:
                temp_df['Mando_Padrao'] = 'N/A'
            df_jogos_list.append(temp_df)
        except Exception as e:
            pass
            
    df_jogos = pd.concat(df_jogos_list, ignore_index=True) if df_jogos_list else pd.DataFrame()
    
    if not df_jogos.empty:
        df_jogos = df_jogos.drop_duplicates(subset=['rodada_id', 'clube_id'])
    
    return df_main, df_jogos

df, df_jogos = load_data()

# --- Processamento ---
if df.empty:
    st.error("⚠️ Nenhum dado encontrado.")
else:
    # Tipagem Segura
    df['atletas.rodada_id'] = pd.to_numeric(df['atletas.rodada_id'], errors='coerce').fillna(0).astype(int)
    df['atletas.clube_id'] = pd.to_numeric(df['atletas.clube_id'], errors='coerce').fillna(0).astype(int)
    
    # Merge com Jogos
    if not df_jogos.empty:
        df_jogos['rodada_id'] = pd.to_numeric(df_jogos['rodada_id'], errors='coerce').fillna(0).astype(int)
        df_jogos['clube_id'] = pd.to_numeric(df_jogos['clube_id'], errors='coerce').fillna(0).astype(int)

        cols_jogo = ['rodada_id', 'clube_id']
        if 'Mando_Padrao' in df_jogos.columns: cols_jogo.append('Mando_Padrao')
        if 'Adversario' in df_jogos.columns: cols_jogo.append('Adversario')
        if 'Estadio' in df_jogos.columns: cols_jogo.append('Estadio')
        if 'Data' in df_jogos.columns: cols_jogo.append('Data')
        if 'Hora' in df_jogos.columns: cols_jogo.append('Hora')

        df = pd.merge(
            df, 
            df_jogos[cols_jogo], 
            left_on=['atletas.rodada_id', 'atletas.clube_id'], 
            right_on=['rodada_id', 'clube_id'], 
            how='left'
        )
    
    if 'Mando_Padrao' not in df.columns: df['Mando_Padrao'] = 'N/A'
    if 'Adversario' not in df.columns: df['Adversario'] = 'N/A'
    df['Mando_Padrao'] = df['Mando_Padrao'].fillna('N/A')
    df['Adversario'] = df['Adversario'].fillna('N/A')

    df = df.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    if 'atletas.entrou_em_campo' in df.columns:
        df['atletas.entrou_em_campo'] = df['atletas.entrou_em_campo'].astype(str).str.lower().isin(['true', '1', '1.0'])

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
    # --- SIDEBAR ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Globais")

    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    if min_rodada == max_rodada:
        sel_rodada_range = (min_rodada, max_rodada)
    else:
        sel_rodada_range = st.sidebar.slider("Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))

    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Preço (C$)", min_preco, max_preco, (min_preco, max_preco))
    
    st.sidebar.markdown("---")
    
    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    all_posicoes = sorted(df['posicao_nome'].dropna().unique())

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    sel_mando = st.sidebar.multiselect("Mando", ['CASA', 'FORA'], default=['CASA', 'FORA'])
    somente_jogaram = st.sidebar.checkbox("Apenas quem jogou?", value=True)

    # --- FILTRAGEM ---
    df_filtrado_base = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]

    if sel_clube: df_filtrado_base = df_filtrado_base[df_filtrado_base['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_filtrado_base = df_filtrado_base[df_filtrado_base['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_filtrado_base = df_filtrado_base[df_filtrado_base['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram: df_filtrado_base = df_filtrado_base[df_filtrado_base['atletas.entrou_em_campo'] == True]
    
    df_filtrado_completo = df_filtrado_base[
        (df_filtrado_base['atletas.preco_num'] >= sel_preco_range[0]) &
        (df_filtrado_base['atletas.preco_num'] <= sel_preco_range[1])
    ]

    # ==========================================
    # --- AGRUPAMENTO (CORRETO) ---
    # ==========================================
    def agrupar_dados(dataframe_input):
        if dataframe_input.empty: return pd.DataFrame()
        
        df_sorted = dataframe_input.sort_values('atletas.rodada_id', ascending=True)
        
        agg_dict = {
            'atletas.pontos_num': 'sum',
            'atletas.preco_num': 'last',
            'atletas.apelido': 'last',
            'atletas.clube.id.full.name': 'last',
            'atletas.clube_id': 'last',
            'posicao_nome': 'last',
            'atletas.foto': 'last',
            'finalizacoes_total': 'last',
            'atletas.jogos_num': 'last'
        }
        for s in todos_scouts: agg_dict[s] = 'last'
            
        df_grouped = df_sorted.groupby('atletas.atleta_id').agg(agg_dict).reset_index()
        df_grouped.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)
        
        return df_grouped

    df_agrupado_geral = agrupar_dados(df_filtrado_completo)
    df_pool_total = agrupar_dados(df_filtrado_base)

    # ==========================================
    # --- DASHBOARD ---
    # ==========================================
    if df_agrupado_geral.empty and df_pool_total.empty:
        st.warning("⚠️ Nenhum jogador encontrado. Ajuste os filtros.")
    else:
        # KPIs
        if not df_agrupado_geral.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Maior Pontuador (Soma)", f"{df_agrupado_geral['pontuacao_total_periodo'].max():.1f}")
            k2.metric("Média Geral (Por Jogo)", f"{df_filtrado_completo['atletas.pontos_num'].mean():.2f}")
            k3.metric("Preço Médio", f"C$ {df_agrupado_geral['atletas.preco_num'].mean():.2f}")
            k4.metric("Jogadores Listados", f"{len(df_agrupado_geral)}")

        st.markdown("---")

        tab_jogos, tab_robo, tab_comparador, tab_capitao, tab_destaques, tab_adversario, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "📅 Jogos da Rodada", "🤖 Robô Escalador", "⚔️ Comparador", "© Capitão", "🏆 Destaques", 
            "🛡️ Raio-X Adversário", "📊 Times", "🏠 Casa vs Fora", "💎 Valorização", "📋 Tabela"
        ])

        # --- ABA 0: JOGOS DA RODADA (NOVA) ---
        with tab_jogos:
            st.header("📅 Confrontos e Análise de Favoritismo")
            
            if not df_jogos.empty:
                rodadas_disp = sorted(df_jogos['rodada_id'].unique())
                rodada_selecionada = st.selectbox("Selecione a Rodada para Visualizar:", rodadas_disp)
                
                # Dados da rodada
                jogos_r = df_jogos[df_jogos['rodada_id'] == rodada_selecionada]
                
                # Estatísticas dos Clubes (Baseado no histórico carregado)
                stats_clubes = df.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])['atletas.pontos_num'].mean().reset_index()
                
                # Loop pelos jogos
                # Precisamos dos nomes dos times. O df_jogos tem 'clube_id' e 'Adversario'.
                # Vamos tentar mapear 'clube_id' para Nome usando o dataframe principal
                mapa_clubes = df[['atletas.clube_id', 'atletas.clube.id.full.name']].drop_duplicates().set_index('atletas.clube_id')['atletas.clube.id.full.name'].to_dict()
                
                # Filtrar jogos onde o time é Mandante para não duplicar (A vs B e B vs A)
                jogos_unicos = jogos_r[jogos_r['Mando_Padrao'] == 'CASA']
                
                if jogos_unicos.empty:
                    st.info("Nenhum jogo encontrado como mandante nesta rodada. Mostrando lista bruta:")
                    st.dataframe(jogos_r)
                else:
                    for _, jogo in jogos_unicos.iterrows():
                        mandante_nome = mapa_clubes.get(jogo['clube_id'], f"ID {jogo['clube_id']}")
                        visitante_nome = jogo['Adversario']
                        estadio = jogo.get('Estadio', 'Local não inf.')
                        data = jogo.get('Data', '')
                        hora = jogo.get('Hora', '')
                        
                        # Buscar stats
                        # Mandante em Casa
                        media_mandante = stats_clubes[
                            (stats_clubes['atletas.clube.id.full.name'] == mandante_nome) & 
                            (stats_clubes['Mando_Padrao'] == 'CASA')
                        ]['atletas.pontos_num'].mean()
                        
                        # Visitante Fora (Tentativa de busca pelo nome do adversário)
                        media_visitante = stats_clubes[
                            (stats_clubes['atletas.clube.id.full.name'] == visitante_nome) & 
                            (stats_clubes['Mando_Padrao'] == 'FORA')
                        ]['atletas.pontos_num'].mean()
                        
                        # Visual do Card
                        with st.container():
                            st.markdown(f"#### 🏟️ {estadio} | {data} {hora}")
                            c1, c2, c3 = st.columns([1, 0.2, 1])
                            
                            with c1:
                                st.markdown(f"<h3 style='text-align: center; color: #4CAF50;'>{mandante_nome}</h3>", unsafe_allow_html=True)
                                if pd.notna(media_mandante):
                                    st.metric("Média em Casa", f"{media_mandante:.1f} pts")
                                else:
                                    st.caption("Sem dados em casa")
                                    
                            with c2:
                                st.markdown("<h2 style='text-align: center;'>X</h2>", unsafe_allow_html=True)
                                
                            with c3:
                                st.markdown(f"<h3 style='text-align: center; color: #FF5252;'>{visitante_nome}</h3>", unsafe_allow_html=True)
                                if pd.notna(media_visitante):
                                    st.metric("Média Fora", f"{media_visitante:.1f} pts")
                                else:
                                    st.caption("Sem dados fora")
                            
                            st.divider()
            else:
                st.warning("Arquivo de confrontos não carregado.")

        # --- ABA 1: ROBÔ ---
        with tab_robo:
            st.header("🤖 Otimizador de Escalação")
            c1, c2 = st.columns(2)
            orcamento = c1.number_input("💰 Orçamento (C$)", value=100.0)
            esquema = c2.selectbox("Formação", ["4-3-3", "3-4-3", "3-5-2", "4-4-2", "5-3-2"])
            
            if st.button("🚀 Escalar Time"):
                esquemas = {"4-3-3": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 3, 'Atacante': 3, 'Técnico': 0}, "3-4-3": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 3, 'Técnico': 0}, "3-5-2": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 5, 'Atacante': 2, 'Técnico': 0}, "4-4-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 4, 'Atacante': 2, 'Técnico': 0}, "5-3-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 3, 'Atacante': 2, 'Técnico': 0}}
                
                col_sort = 'pontuacao_total_periodo'
                pool = df_pool_total.sort_values(col_sort, ascending=False)
                
                time_atual = []
                for pos, qtd in esquemas[esquema].items():
                    if qtd > 0:
                        melhores = pool[pool['posicao_nome'] == pos].head(qtd)
                        time_atual.append(melhores)
                
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
                                    ratio = (sair[col_sort] - entrar[col_sort]) / econ
                                    if ratio < melhor_ratio: melhor_ratio, melhor_troca = ratio, (idx, entrar)
                        if melhor_troca:
                            df_time = df_time.drop(melhor_troca[0])
                            df_time = pd.concat([df_time, melhor_troca[1].to_frame().T])
                            custo = df_time['atletas.preco_num'].sum()
                        else: break
                        loop += 1
                    
                    st.success(f"✅ Time Escalado! Custo: C$ {custo:.2f}")
                    ordem = {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 5}
                    df_time['ordem'] = df_time['posicao_nome'].map(ordem)
                    cols = st.columns(5)
                    i = 0
                    for _, row in df_time.sort_values('ordem').iterrows():
                        with cols[i % 5]:
                            st.image(formatar_foto(row.get('atletas.foto', '')), width=80)
                            st.markdown(f"**{row['posicao_nome']}**")
                            st.caption(row['atletas.apelido'])
                            st.write(f"C$ {row['atletas.preco_num']:.1f}")
                            st.metric("Pontos", f"{row[col_sort]:.1f}")
                            st.divider()
                        i += 1
                else: st.warning("Dados insuficientes.")

        # --- ABA 2: COMPARADOR ---
        with tab_comparador:
            st.header("⚔️ Comparador Mano a Mano")
            c1, c2 = st.columns(2)
            
            busca1 = c1.text_input("Filtrar Jogador 1", "").strip().lower()
            busca2 = c2.text_input("Filtrar Jogador 2", "").strip().lower()
            
            nomes = sorted(df_pool_total['atletas.apelido'].unique())
            lista1 = [n for n in nomes if busca1 in n.lower()] if busca1 else nomes
            lista2 = [n for n in nomes if busca2 in n.lower()] if busca2 else nomes
            
            p1_n = c1.selectbox("Selecione Jogador 1", lista1, index=0 if lista1 else None)
            p2_n = c2.selectbox("Selecione Jogador 2", lista2, index=min(1, len(lista2)-1) if lista2 else None)
            
            if p1_n and p2_n:
                d1 = df_pool_total[df_pool_total['atletas.apelido'] == p1_n].iloc[0]
                d2 = df_pool_total[df_pool_total['atletas.apelido'] == p2_n].iloc[0]
                cats = ['Pontos Totais', 'Gols', 'Assist', 'Finalizações', 'Desarmes', 'Jogos']
                
                jogos1 = d1['atletas.jogos_num'] if 'atletas.jogos_num' in d1 else 0
                jogos2 = d2['atletas.jogos_num'] if 'atletas.jogos_num' in d2 else 0
                
                v1 = [d1['pontuacao_total_periodo'], d1['G'], d1['A'], d1['finalizacoes_total'], d1['DS'], jogos1]
                v2 = [d2['pontuacao_total_periodo'], d2['G'], d2['A'], d2['finalizacoes_total'], d2['DS'], jogos2]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(r=v1, theta=cats, fill='toself', name=p1_n, line_color='#00CC96'))
                fig.add_trace(go.Scatterpolar(r=v2, theta=cats, fill='toself', name=p2_n, line_color='#EF553B'))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True)), title="Comparativo Direto")
                st.plotly_chart(fig, use_container_width=True)

        # --- ABA 3: CAPITÃO ---
        with tab_capitao:
            st.header("© Capitão de Segurança")
            busca_cap = st.text_input("Buscar Jogador na Lista Abaixo", "").strip().lower()
            
            if not df_jogos.empty:
                rds = sorted(df_jogos['rodada_id'].unique())
                rodada = st.selectbox("Simular Rodada:", rds)
                
                df_heat = df_filtrado_completo[df_filtrado_completo['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                jogos = df_jogos[df_jogos['rodada_id'] == rodada][['clube_id', 'Adversario', 'Mando_Padrao']]
                
                if not df_pool_total.empty:
                    df_cap = pd.merge(df_pool_total, jogos, left_on='atletas.clube_id', right_on='clube_id', how='inner')
                    
                    if not df_cap.empty:
                        df_final = pd.merge(df_cap, df_heat, on=['Adversario', 'posicao_nome'], how='left')
                        df_final['media_cedida_adv'] = df_final['atletas.pontos_num'].fillna(0)
                        
                        # Score Simples
                        df_final['score_seguranca'] = df_final['pontuacao_total_periodo'] + (df_final['media_cedida_adv'] * 2)
                        
                        if busca_cap:
                            df_final = df_final[df_final['atletas.apelido'].str.lower().str.contains(busca_cap)]
                        
                        st.dataframe(
                            df_final[['atletas.apelido', 'posicao_nome', 'Adversario', 'pontuacao_total_periodo', 'media_cedida_adv', 'score_seguranca']]
                            .sort_values('score_seguranca', ascending=False)
                            .rename(columns={'pontuacao_total_periodo': 'Pontos Totais', 'media_cedida_adv': 'Fragilidade Adv', 'score_seguranca': 'Score Sugerido'}),
                            use_container_width=True, hide_index=True
                        )
                    else: st.warning("Sem jogos previstos.")
            else: st.warning("Sem confrontos.")

        # --- ABA 4: DESTAQUES ---
        with tab_destaques:
            st.markdown(f"#### 🔥 Líderes (Acumulado)")
            def render_d(l, c, cont):
                if df_agrupado_geral.empty or c not in df_agrupado_geral or df_agrupado_geral[c].sum()==0: 
                    cont.info(f"{l}: 0"); return
                idx = df_agrupado_geral[c].idxmax()
                r = df_agrupado_geral.loc[idx]
                with cont:
                    st.markdown(f"**{l}**")
                    c1, c2 = st.columns([1,2])
                    c1.image(formatar_foto(r.get('atletas.foto','')), width=70)
                    c2.caption(f"{r['atletas.apelido']}\n{r['atletas.clube.id.full.name']}")
                    st.metric("Total", int(r[c]))
                    st.divider()
            
            c1, c2, c3, c4 = st.columns(4)
            render_d("Gols", 'G', c1); render_d("Assist", 'A', c2); render_d("Trave", 'FT', c3); render_d("Fin. Def", 'FD', c4)
            c1, c2, c3, c4 = st.columns(4)
            render_d("Desarmes", 'DS', c1); render_d("SG", 'SG', c2); render_d("Defesas", 'DE', c3); render_d("Pen. Def", 'DP', c4)
            n1, n2, n3, n4 = st.columns(4)
            render_d("Gols Sofridos (GS)", 'GS', n1); render_d("Faltas Cometidas (FC)", 'FC', n2); render_d("Cartão Amarelo (CA)", 'CA', n3); render_d("Cartão Vermelho (CV)", 'CV', n4)

        # --- ABA 5: RAIO-X (4 GRAFICOS - Melhor Visualização) ---
        with tab_adversario:
            st.subheader("🔥 Raio-X: Quem cede mais pontos?")
            if 'Adversario' in df_filtrado_completo.columns and not df_filtrado_completo['Adversario'].isin(['N/A']).all():
                d = df_filtrado_completo[df_filtrado_completo['Adversario']!='N/A'].groupby(['Adversario','posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                def plot_h(pos, tit, cor):
                    dp = d[d['posicao_nome'].isin(pos)]
                    if dp.empty: return
                    p = dp.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                    p['T'] = p.sum(axis=1); p = p.sort_values('T').drop(columns='T')
                    st.plotly_chart(px.imshow(p, text_auto=".1f", color_continuous_scale=cor, title=tit), use_container_width=True)
                
                c1, c2, c3, c4 = st.columns(4)
                with c1: plot_h(['Goleiro'], "Goleiros", "Blues")
                with c2: plot_h(['Zagueiro','Lateral'], "Defesa", "Greens")
                with c3: plot_h(['Meia'], "Meias", "Oranges")
                with c4: plot_h(['Atacante'], "Ataque", "Reds")
            else: st.warning("Dados insuficientes.")

        # --- ABA 6: TIMES ---
        with tab_times:
            if not df_filtrado_completo.empty:
                g = df_filtrado_completo.groupby('atletas.clube.id.full.name')[['atletas.pontos_num', 'finalizacoes_total']].mean().reset_index()
                c1, c2 = st.columns(2)
                c1.plotly_chart(px.bar(g.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h', title="Média Pontos"), use_container_width=True)
                c2.plotly_chart(px.bar(g.sort_values('finalizacoes_total'), x='finalizacoes_total', y='atletas.clube.id.full.name', orientation='h', title="Média Finalizações", color_discrete_sequence=['red']), use_container_width=True)

        # --- ABA 7: CASA/FORA ---
        with tab_scouts:
            if 'Mando_Padrao' in df_filtrado_completo.columns and not df_filtrado_completo.empty:
                g = df_filtrado_completo.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                c1, c2 = st.columns(2)
                with c1: st.plotly_chart(px.bar(g, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group', title="Ataque"), use_container_width=True)
                with c2: st.plotly_chart(px.bar(g, x='atletas.clube.id.full.name', y='scouts_defensivos_total', color='Mando_Padrao', barmode='group', title="Defesa"), use_container_width=True)

        # --- ABA 8: VALORIZAÇÃO ---
        with tab_valorizacao:
            if not df_filtrado_completo.empty:
                st.plotly_chart(px.scatter(df_filtrado_completo, x='atletas.preco_num', y='atletas.pontos_num', color='posicao_nome', size='tamanho_visual', hover_name='atletas.apelido', title="Preço x Pontuação (Jogo a Jogo)"), use_container_width=True)

        # --- ABA 9: TABELA ---
        with tab_tabela:
            st.subheader("Tabela Consolidada")
            busca_tab = st.text_input("Buscar na Tabela", "").strip().lower()
            df_show = df_agrupado_geral
            if busca_tab:
                df_show = df_show[df_show['atletas.apelido'].str.lower().str.contains(busca_tab)]
            
            # Sem Pontuação Básica
            cols = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.preco_num', 'pontuacao_total_periodo'] + todos_scouts
            st.dataframe(df_show[cols].sort_values('pontuacao_total_periodo', ascending=False), use_container_width=True, hide_index=True)
