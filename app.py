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
            temp.columns = temp.columns.str.strip() # Limpeza de espaços
            dfs.append(temp)
        except Exception as e:
            st.warning(f"Erro ao ler {f}: {e}")
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    # Remove duplicatas de leitura bruta
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
    st.error("⚠️ Nenhum dado encontrado. Verifique se os arquivos CSV estão na pasta.")
else:
    # Tipagem Segura
    df['atletas.rodada_id'] = pd.to_numeric(df['atletas.rodada_id'], errors='coerce').fillna(0).astype(int)
    df['atletas.clube_id'] = pd.to_numeric(df['atletas.clube_id'], errors='coerce').fillna(0).astype(int)
    
    # Merge com Jogos (Blindagem contra erro de Coluna)
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
    
    # Garante que as colunas existam para não dar KeyError
    if 'Mando_Padrao' not in df.columns: df['Mando_Padrao'] = 'N/A'
    if 'Adversario' not in df.columns: df['Adversario'] = 'N/A'
    
    # Preenche N/A
    df['Mando_Padrao'] = df['Mando_Padrao'].fillna('N/A')
    df['Adversario'] = df['Adversario'].fillna('N/A')

    df = df.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    if 'atletas.entrou_em_campo' in df.columns:
        df['atletas.entrou_em_campo'] = df['atletas.entrou_em_campo'].astype(str).str.lower().isin(['true', '1', '1.0'])

    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # Lista de Scouts Oficiais
    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns: df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Auxiliares Visuais
    df['tamanho_visual'] = df['atletas.pontos_num'].apply(lambda x: max(1.0, x))
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
    # Filtro de Período e Categorias
    df_filtrado_base = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]

    if sel_clube: df_filtrado_base = df_filtrado_base[df_filtrado_base['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_filtrado_base = df_filtrado_base[df_filtrado_base['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_filtrado_base = df_filtrado_base[df_filtrado_base['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram: df_filtrado_base = df_filtrado_base[df_filtrado_base['atletas.entrou_em_campo'] == True]
    
    # Filtro com Preço (Para visualizações gerais)
    df_filtrado_completo = df_filtrado_base[
        (df_filtrado_base['atletas.preco_num'] >= sel_preco_range[0]) &
        (df_filtrado_base['atletas.preco_num'] <= sel_preco_range[1])
    ]

    # ==========================================
    # --- AGRUPAMENTO CORRIGIDO (O Segredo do Danilo) ---
    # ==========================================
    def agrupar_dados(dataframe_input):
        if dataframe_input.empty: return pd.DataFrame()
        
        # Ordena por rodada crescente
        df_sorted = dataframe_input.sort_values('atletas.rodada_id', ascending=True)
        
        # Definição das agregações
        agg_dict = {
            'atletas.pontos_num': 'sum', # PONTOS: Somamos (R1 + R2)
            'atletas.preco_num': 'last', # PREÇO: Último valor
            'atletas.apelido': 'last',
            'atletas.clube.id.full.name': 'last',
            'atletas.clube_id': 'last',
            'posicao_nome': 'last',
            'atletas.foto': 'last',
            'finalizacoes_total': 'last' # SCOUT: Como é acumulado, pegamos o último (last)
        }
        
        # Todos os scouts individuais também são 'last' (acumulados na fonte)
        for s in todos_scouts:
            agg_dict[s] = 'last'
            
        # Agrupa
        df_grouped = df_sorted.groupby('atletas.atleta_id').agg(agg_dict).reset_index()
        
        # Renomeia para ficar claro
        df_grouped.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)
        
        return df_grouped

    # Gera os dados agrupados
    df_agrupado_geral = agrupar_dados(df_filtrado_completo)
    df_pool_total = agrupar_dados(df_filtrado_base) # Sem filtro de preço para o Robô

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

        tab_robo, tab_comparador, tab_capitao, tab_destaques, tab_adversario, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🤖 Robô Escalador", "⚔️ Comparador", "© Capitão", "🏆 Destaques", 
            "🛡️ Raio-X Adversário", "📊 Times", "🏠 Casa vs Fora", "💎 Valorização", "📋 Tabela"
        ])

        # --- ABA 1: ROBÔ ---
        with tab_robo:
            st.header("🤖 Otimizador de Escalação")
            c1, c2 = st.columns(2)
            orcamento = c1.number_input("💰 Orçamento (C$)", value=100.0)
            esquema = c2.selectbox("Formação", ["4-3-3", "3-4-3", "3-5-2", "4-4-2", "5-3-2"])
            
            if st.button("🚀 Escalar Time"):
                esquemas = {"4-3-3": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 3, 'Atacante': 3, 'Técnico': 0}, "3-4-3": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 3, 'Técnico': 0}, "3-5-2": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 5, 'Atacante': 2, 'Técnico': 0}, "4-4-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 4, 'Atacante': 2, 'Técnico': 0}, "5-3-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 3, 'Atacante': 2, 'Técnico': 0}}
                
                col_sort = 'pontuacao_total_periodo' # Foco total em pontos
                pool = df_pool_total.sort_values(col_sort, ascending=False)
                
                time_atual = []
                for pos, qtd in esquemas[esquema].items():
                    if qtd > 0:
                        melhores = pool[pool['posicao_nome'] == pos].head(qtd)
                        time_atual.append(melhores)
                
                if time_atual:
                    df_time = pd.concat(time_atual)
                    custo = df_time['atletas.preco_num'].sum()
                    
                    # Otimização Gulosa
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

        # --- ABA 2: COMPARADOR (FILTROS SEPARADOS) ---
        with tab_comparador:
            st.header("⚔️ Comparador Mano a Mano")
            c1, c2 = st.columns(2)
            
            # Filtros de Texto
            busca1 = c1.text_input("Filtrar Jogador 1", "").strip().lower()
            busca2 = c2.text_input("Filtrar Jogador 2", "").strip().lower()
            
            lista_base = sorted(df_pool_total['atletas.apelido'].unique())
            lista1 = [n for n in lista_base if busca1 in n.lower()] if busca1 else lista_base
            lista2 = [n for n in lista_base if busca2 in n.lower()] if busca2 else lista_base
            
            p1_n = c1.selectbox("Selecione Jogador 1", lista1, index=0 if lista1 else None)
            p2_n = c2.selectbox("Selecione Jogador 2", lista2, index=min(1, len(lista2)-1) if lista2 else None)
            
            if p1_n and p2_n:
                d1 = df_pool_total[df_pool_total['atletas.apelido'] == p1_n].iloc[0]
                d2 = df_pool_total[df_pool_total['atletas.apelido'] == p2_n].iloc[0]
                cats = ['Pontos Totais', 'Gols', 'Assist', 'Finalizações', 'Desarmes', 'Jogos']
                v1 = [d1['pontuacao_total_periodo'], d1['G'], d1['A'], d1['finalizacoes_total'], d1['DS'], d1['atletas.jogos_num']]
                v2 = [d2['pontuacao_total_periodo'], d2['G'], d2['A'], d2['finalizacoes_total'], d2['DS'], d2['atletas.jogos_num']]
                
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
                
                # Mapa de Calor (Fragilidade)
                df_heat = df_filtrado_completo[df_filtrado_completo['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                
                # Jogos Futuros
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

        # --- ABA 5: RAIO-X (VOLTOU AO ORIGINAL) ---
        with tab_adversario:
            st.subheader("🔥 Raio-X: Quem cede mais pontos?")
            st.info("Mapa geral: Linha = Adversário, Coluna = Posição. Quanto mais vermelho, mais pontos cede.")
            
            if 'Adversario' in df_filtrado_completo.columns:
                df_heat = df_filtrado_completo[df_filtrado_completo['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                
                if not df_heat.empty:
                    heatmap_data = df_heat.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                    # Ordena
                    heatmap_data['Total'] = heatmap_data.sum(axis=1)
                    heatmap_data = heatmap_data.sort_values('Total', ascending=True).drop(columns='Total')
                    
                    fig_heat = px.imshow(heatmap_data, text_auto=".1f", aspect="auto", color_continuous_scale="Reds")
                    fig_heat.update_layout(height=800)
                    st.plotly_chart(fig_heat, use_container_width=True)
                else: st.warning("Dados insuficientes para o mapa.")

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
            df_display = df_show[cols].sort_values('pontuacao_total_periodo', ascending=False)
            df_display.columns = ['Apelido', 'Clube', 'Posição', 'Preço', 'Pontos Totais'] + todos_scouts
            st.dataframe(df_display, use_container_width=True, hide_index=True)

