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

# Executa carregamento
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

        df = pd.merge(
            df, 
            df_jogos[cols_jogo], 
            left_on=['atletas.rodada_id', 'atletas.clube_id'], 
            right_on=['rodada_id', 'clube_id'], 
            how='left'
        )
    
    # Preenche Falhas de Merge
    if 'Mando_Padrao' not in df.columns: df['Mando_Padrao'] = 'N/A'
    if 'Adversario' not in df.columns: df['Adversario'] = 'N/A'
    df['Mando_Padrao'] = df['Mando_Padrao'].fillna('N/A')
    df['Adversario'] = df['Adversario'].fillna('N/A')

    df = df.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    if 'atletas.entrou_em_campo' in df.columns:
        df['atletas.entrou_em_campo'] = df['atletas.entrou_em_campo'].astype(str).str.lower().isin(['true', '1', '1.0'])

    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # Preenche Scouts
    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns: df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Cálculo da Pontuação Básica (Por Linha - Para visualização bolha)
    df['pontuacao_basica'] = (
        (df['DS'] * 1.2) + (df['DE'] * 1.0) + (df['SG'] * 5.0) + 
        (df['FS'] * 0.5) + (df['FD'] * 1.2) + (df['FT'] * 3.0) + 
        (df['FF'] * 0.8) + (df['PS'] * 1.0) + (df['DP'] * 7.0)
    )
    df['tamanho_visual'] = df['pontuacao_basica'].apply(lambda x: max(1.0, x))
    
    # Auxiliares
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR (Filtros Globais) ---
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

    # --- APLICAÇÃO DOS FILTROS ---
    # Filtragem Base (Rodada + Categóricos)
    df_filtrado = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]

    if sel_clube: df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_filtrado = df_filtrado[df_filtrado['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram: df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]
    
    # Filtragem Preço (separada para uso no Robô)
    df_filtrado_preco = df_filtrado[
        (df_filtrado['atletas.preco_num'] >= sel_preco_range[0]) &
        (df_filtrado['atletas.preco_num'] <= sel_preco_range[1])
    ]

    # ==========================================
    # --- AGRUPAMENTO (LÓGICA CORRETA: SOMA + SNAPSHOT) ---
    # ==========================================
    def processar_agrupamento(dataframe_input):
        if dataframe_input.empty: return pd.DataFrame()
        
        # 1. PONTUAÇÃO: Somamos todas as rodadas
        df_pontos = dataframe_input.groupby('atletas.atleta_id')['atletas.pontos_num'].sum().reset_index()
        df_pontos.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)
        
        # 2. SCOUTS E METADADOS: Pegamos o SNAPSHOT da ÚLTIMA rodada do período
        # Isso garante que não somamos gols acumulados. Pegamos o valor mais recente.
        df_snapshot = dataframe_input.sort_values('atletas.rodada_id', ascending=False).drop_duplicates('atletas.atleta_id')
        
        # 3. MERGE
        df_final = pd.merge(df_snapshot, df_pontos, on='atletas.atleta_id', how='left')
        
        # 4. CÁLCULO PONTUAÇÃO BÁSICA (Baseado no SCOUT ACUMULADO do snapshot)
        # Como o snapshot já traz os scouts acumulados (ex: 4 gols), a básica será correta.
        df_final['pontuacao_basica_atual'] = (
            (df_final['DS'] * 1.2) + (df_final['DE'] * 1.0) + (df_final['SG'] * 5.0) + 
            (df_final['FS'] * 0.5) + (df_final['FD'] * 1.2) + (df_final['FT'] * 3.0) + 
            (df_final['FF'] * 0.8) + (df_final['PS'] * 1.0) + (df_final['DP'] * 7.0)
        )
        return df_final

    # Dados para Tabela/Destaques (respeita preço)
    df_agrupado = processar_agrupamento(df_filtrado_preco)
    
    # Dados para Robô/Comparador (ignora filtro de preço para dar mais opções)
    df_robo_consolidado = processar_agrupamento(df_filtrado)

    # ==========================================
    # --- DASHBOARD ---
    # ==========================================
    if df_agrupado.empty:
        st.warning("⚠️ Nenhum jogador encontrado.")
    else:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador (Soma)", f"{df_agrupado['pontuacao_total_periodo'].max():.1f}")
        k2.metric("Média Geral (Por Jogo)", f"{df_filtrado_preco['atletas.pontos_num'].mean():.2f}")
        k3.metric("Pontuação Básica (Acumulada)", f"{df_agrupado['pontuacao_basica_atual'].mean():.2f}")
        k4.metric("Jogadores", f"{len(df_agrupado)}")

        st.markdown("---")

        tab_robo, tab_comparador, tab_capitao, tab_destaques, tab_adversario, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🤖 Robô Escalador", "⚔️ Comparador", "© Capitão", "🏆 Destaques", 
            "🛡️ Raio-X Adversário", "📊 Times", "🏠 Casa vs Fora", "💎 Valorização", "📋 Tabela"
        ])

        # --- ABA 1: ROBÔ ---
        with tab_robo:
            st.header("🤖 Otimizador de Escalação")
            c1, c2, c3 = st.columns(3)
            orcamento = c1.number_input("💰 Orçamento (C$)", value=100.0)
            esquema = c2.selectbox("Formação", ["4-3-3", "3-4-3", "3-5-2", "4-4-2", "5-3-2"])
            criterio = c3.selectbox("Focar em:", ["Pontuação Básica", "Pontuação Total"])
            col_sort = 'pontuacao_basica_atual' if criterio == "Pontuação Básica" else 'pontuacao_total_periodo'

            if st.button("🚀 Escalar Time"):
                esquemas = {"4-3-3": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 3, 'Atacante': 3, 'Técnico': 0}, "3-4-3": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 3, 'Técnico': 0}, "3-5-2": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 5, 'Atacante': 2, 'Técnico': 0}, "4-4-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 4, 'Atacante': 2, 'Técnico': 0}, "5-3-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 3, 'Atacante': 2, 'Técnico': 0}}
                pool = df_robo_consolidado.sort_values(col_sort, ascending=False)
                time_atual = []
                for pos, qtd in esquemas[esquema].items():
                    if qtd > 0:
                        melhores = pool[pool['posicao_nome'] == pos].head(qtd)
                        time_atual.append(melhores)
                
                if time_atual:
                    df_time = pd.concat(time_atual)
                    custo = df_time['atletas.preco_num'].sum()
                    
                    loop = 0
                    while custo > orcamento and loop < 200:
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
                        with cols[i%5]:
                            st.image(formatar_foto(row.get('atletas.foto', '')), width=80)
                            st.markdown(f"**{row['posicao_nome']}**")
                            st.caption(row['atletas.apelido'])
                            st.write(f"C$ {row['atletas.preco_num']:.1f}")
                            st.metric("Pontos", f"{row[col_sort]:.1f}")
                            st.divider()
                        i+=1
                else: st.warning("Dados insuficientes.")

        # --- ABA 2: COMPARADOR ---
        with tab_comparador:
            st.header("⚔️ Comparador Mano a Mano")
            filtro_comp = st.text_input("Buscar Jogador (Comparador)", placeholder="Digite o nome...").strip().lower()
            
            pool_comp = df_robo_consolidado
            if filtro_comp:
                pool_comp = pool_comp[pool_comp['atletas.apelido'].str.lower().str.contains(filtro_comp)]
            
            nomes = sorted(pool_comp['atletas.apelido'].unique())
            if not nomes: st.warning("Nenhum jogador encontrado."); st.stop()
            
            c1, c2 = st.columns(2)
            p1_n = c1.selectbox("Jogador 1", nomes, index=0)
            p2_n = c2.selectbox("Jogador 2", nomes, index=min(1, len(nomes)-1))
            
            if p1_n and p2_n:
                d1 = df_robo_consolidado[df_robo_consolidado['atletas.apelido'] == p1_n].iloc[0]
                d2 = df_robo_consolidado[df_robo_consolidado['atletas.apelido'] == p2_n].iloc[0]
                cats = ['Pontos Totais', 'Pontuação Básica', 'Gols', 'Assist', 'Finalizações', 'Desarmes']
                v1 = [d1['pontuacao_total_periodo'], d1['pontuacao_basica_atual'], d1['G'], d1['A'], d1['finalizacoes_total'], d1['DS']]
                v2 = [d2['pontuacao_total_periodo'], d2['pontuacao_basica_atual'], d2['G'], d2['A'], d2['finalizacoes_total'], d2['DS']]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(r=v1, theta=cats, fill='toself', name=p1_n, line_color='#00CC96'))
                fig.add_trace(go.Scatterpolar(r=v2, theta=cats, fill='toself', name=p2_n, line_color='#EF553B'))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True)), title="Comparativo Direto")
                st.plotly_chart(fig, use_container_width=True)

        # --- ABA 3: CAPITÃO ---
        with tab_capitao:
            st.header("© Capitão de Segurança")
            filtro_cap = st.text_input("Buscar Jogador (Capitão)", placeholder="Digite o nome...").strip().lower()
            
            if not df_jogos.empty:
                rds = sorted(df_jogos['rodada_id'].unique())
                rodada = st.selectbox("Simular Rodada:", rds)
                
                df_heat = df_filtrado[df_filtrado['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                jogos = df_jogos[df_jogos['rodada_id'] == rodada][['clube_id', 'Adversario', 'Mando_Padrao']]
                
                # Base de jogadores (filtrada por nome se houver input)
                base_cap = df_robo_consolidado
                if filtro_cap:
                    base_cap = base_cap[base_cap['atletas.apelido'].str.lower().str.contains(filtro_cap)]

                df_cap = pd.merge(base_cap, jogos, left_on='atletas.clube_id', right_on='clube_id', how='inner')
                
                if not df_cap.empty:
                    df_final = pd.merge(df_cap, df_heat, on=['Adversario', 'posicao_nome'], how='left')
                    df_final['media_cedida_adv'] = df_final['atletas.pontos_num'].fillna(0)
                    df_final['score_seguranca'] = df_final['pontuacao_basica_atual'] + (df_final['media_cedida_adv'] * 2) 
                    
                    st.dataframe(
                        df_final[['atletas.apelido', 'posicao_nome', 'Adversario', 'pontuacao_basica_atual', 'media_cedida_adv', 'score_seguranca']]
                        .sort_values('score_seguranca', ascending=False)
                        .rename(columns={'pontuacao_basica_atual': 'Pont. Básica', 'media_cedida_adv': 'Fragilidade Adv', 'score_seguranca': 'Score'}),
                        use_container_width=True, hide_index=True
                    )
                else: st.warning("Sem jogos previstos.")
            else: st.warning("Sem confrontos.")

        # --- ABA 4: DESTAQUES (LAYOUT ORIGINAL COM FOTO) ---
        with tab_destaques:
            st.markdown(f"#### 🔥 Líderes (Acumulado)")
            def render_d(l, c, cont):
                if df_agrupado[c].sum()==0: cont.info(f"{l}: 0"); return
                idx = df_agrupado[c].idxmax()
                r = df_agrupado.loc[idx]
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

        # --- ABA 5: RAIO-X (LAYOUT ORIGINAL) ---
        with tab_adversario:
            st.subheader("🔥 Raio-X: Quem cede mais pontos?")
            if 'Adversario' in df_filtrado_preco.columns:
                df_heat = df_filtrado_preco[df_filtrado_preco['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                heatmap_data = df_heat.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                heatmap_data['Total'] = heatmap_data.sum(axis=1)
                heatmap_data = heatmap_data.sort_values('Total', ascending=True).drop(columns='Total')
                fig_heat = px.imshow(heatmap_data, text_auto=".1f", aspect="auto", color_continuous_scale="Reds")
                fig_heat.update_layout(height=800)
                st.plotly_chart(fig_heat, use_container_width=True)

        # --- ABA 6: TIMES (LAYOUT ORIGINAL) ---
        with tab_times:
            club_stats = df_filtrado_preco.groupby('atletas.clube.id.full.name').agg({'atletas.pontos_num': 'mean', 'finalizacoes_total': 'sum'}).reset_index()
            c1, c2 = st.columns(2)
            with c1: st.plotly_chart(px.bar(club_stats.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h', title="Média Pontos"), use_container_width=True)
            with c2: st.plotly_chart(px.bar(club_stats.sort_values('finalizacoes_total'), x='finalizacoes_total', y='atletas.clube.id.full.name', orientation='h', title="Volume Ofensivo", color_discrete_sequence=['red']), use_container_width=True)

        # --- ABA 7: CASA/FORA (LAYOUT ORIGINAL) ---
        with tab_scouts:
            if 'Mando_Padrao' in df_filtrado_preco.columns:
                grp = df_filtrado_preco.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                c1, c2 = st.columns(2)
                with c1: st.plotly_chart(px.bar(grp, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group', title="Ataque"), use_container_width=True)
                with c2: st.plotly_chart(px.bar(grp, x='atletas.clube.id.full.name', y='scouts_defensivos_total', color='Mando_Padrao', barmode='group', title="Defesa"), use_container_width=True)

        # --- ABA 8: VALORIZAÇÃO (LAYOUT ORIGINAL) ---
        with tab_valorizacao:
            st.plotly_chart(px.scatter(df_filtrado_preco, x='atletas.preco_num', y='atletas.pontos_num', color='posicao_nome', size='tamanho_visual', hover_name='atletas.apelido', title="Preço x Pontuação"), use_container_width=True)

        # --- ABA 9: TABELA ---
        with tab_tabela:
            st.subheader("Tabela Consolidada")
            filtro_tab = st.text_input("Buscar Jogador (Tabela)", placeholder="Nome...").strip().lower()
            df_show = df_agrupado
            if filtro_tab:
                df_show = df_show[df_show['atletas.apelido'].str.lower().str.contains(filtro_tab)]
            
            cols = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.preco_num', 'pontuacao_total_periodo', 'pontuacao_basica_atual'] + todos_scouts
            df_show = df_show[cols].sort_values('pontuacao_total_periodo', ascending=False)
            df_show.columns = ['Apelido', 'Clube', 'Posição', 'Preço', 'Pontos Totais', 'Pontuação Básica'] + todos_scouts
            st.dataframe(df_show, use_container_width=True, hide_index=True)
