import streamlit as st
import pandas as pd
import glob
import plotly.express as px
import plotly.graph_objects as go

# --- Configurações Iniciais (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
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
            # Limpa nomes das colunas (remove espaços extras)
            temp.columns = temp.columns.str.strip()
            dfs.append(temp)
        except Exception as e:
            st.warning(f"Erro ao ler {f}: {e}")
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    # Remove duplicatas de leitura
    if not df_main.empty:
        df_main = df_main.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    # 2. Carregar Confrontos
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos_list = []
    
    for f in confronto_files:
        try:
            temp_df = pd.read_csv(f)
            temp_df.columns = temp_df.columns.str.strip() # Limpeza crucial
            
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

# --- Processamento e Tratamento ---
if df.empty:
    st.error("⚠️ Nenhum dado encontrado. Verifique se os arquivos CSV estão na pasta.")
else:
    # Tipagem Segura
    df['atletas.rodada_id'] = pd.to_numeric(df['atletas.rodada_id'], errors='coerce').fillna(0).astype(int)
    df['atletas.clube_id'] = pd.to_numeric(df['atletas.clube_id'], errors='coerce').fillna(0).astype(int)
    
    # Merge com Jogos (Blindado contra KeyError)
    if not df_jogos.empty:
        df_jogos['rodada_id'] = pd.to_numeric(df_jogos['rodada_id'], errors='coerce').fillna(0).astype(int)
        df_jogos['clube_id'] = pd.to_numeric(df_jogos['clube_id'], errors='coerce').fillna(0).astype(int)

        # Verifica se as colunas existem antes do merge
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
    
    # Garante que as colunas existam mesmo se o merge falhar
    if 'Mando_Padrao' not in df.columns: df['Mando_Padrao'] = 'N/A'
    if 'Adversario' not in df.columns: df['Adversario'] = 'N/A'
    
    # Preenche N/A gerados pelo merge
    df['Mando_Padrao'] = df['Mando_Padrao'].fillna('N/A')
    df['Adversario'] = df['Adversario'].fillna('N/A')

    df = df.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    # Entrou em Campo
    if 'atletas.entrou_em_campo' in df.columns:
        df['atletas.entrou_em_campo'] = df['atletas.entrou_em_campo'].astype(str).str.lower().isin(['true', '1', '1.0'])

    # Mapa de Posições
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # Preenche Scouts
    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns: df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- CÁLCULO DA PONTUAÇÃO BÁSICA (Por Rodada - Para visualização de bolhas) ---
    # Somente positivos, ignorando G e A
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
    # --- SIDEBAR ---
    # ==========================================
    st.sidebar.header("🔍 Pesquisa & Filtros")
    
    busca_nome = st.sidebar.text_input("🕵️ Buscar Jogador (Nome)", placeholder="Ex: Hulk, Veiga...").strip().lower()
    st.sidebar.markdown("---")

    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    if min_rodada == max_rodada:
        sel_rodada_range = (min_rodada, max_rodada)
    else:
        sel_rodada_range = st.sidebar.slider("Intervalo de Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))

    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Faixa de Preço", min_preco, max_preco, (min_preco, max_preco))
    
    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    all_posicoes = sorted(df['posicao_nome'].dropna().unique())

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    sel_mando = st.sidebar.multiselect("Mando", ['CASA', 'FORA'], default=['CASA', 'FORA'])
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # --- APLICAÇÃO DOS FILTROS ---
    df_filtrado = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]

    if sel_clube: df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_filtrado = df_filtrado[df_filtrado['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram: df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]
    
    df_filtrado = df_filtrado[
        (df_filtrado['atletas.preco_num'] >= sel_preco_range[0]) &
        (df_filtrado['atletas.preco_num'] <= sel_preco_range[1])
    ]

    if busca_nome:
        df_filtrado = df_filtrado[
            df_filtrado['atletas.apelido'].str.lower().str.contains(busca_nome) | 
            df_filtrado['atletas.clube.id.full.name'].str.lower().str.contains(busca_nome)
        ]

    # ==========================================
    # --- AGRUPAMENTO (LÓGICA CORRIGIDA) ---
    # ==========================================
    def agrupar_dados(dataframe_base):
        if dataframe_base.empty: return pd.DataFrame()
        
        # 1. Agrupa somando TUDO (Pontos e Scouts)
        cols_to_sum = ['atletas.pontos_num'] + todos_scouts + ['finalizacoes_total']
        
        # Agrupa mantendo ID, Nome, Clube ID, Foto, Posição
        # Importante: Mantemos 'atletas.clube_id' no group by para não perder a referência para o Capitão
        df_grouped = dataframe_base.groupby(
            ['atletas.atleta_id', 'atletas.apelido', 'atletas.clube.id.full.name', 'atletas.clube_id', 'posicao_nome', 'atletas.foto']
        )[cols_to_sum].sum().reset_index()
        
        # Renomeia pontos para total
        df_grouped.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)

        # 2. Pega o Preço da ÚLTIMA rodada (Snapshot)
        df_last = dataframe_base.sort_values('atletas.rodada_id', ascending=False).drop_duplicates('atletas.atleta_id')
        df_prices = df_last[['atletas.atleta_id', 'atletas.preco_num']]
        
        # Junta Preço com os Totais
        df_final = pd.merge(df_grouped, df_prices, on='atletas.atleta_id', how='left')

        # 3. Recalcula PONTUAÇÃO BÁSICA sobre os SCOUTS SOMADOS
        # Agora a matemática bate: (Total DS * 1.2) + (Total SG * 5.0)...
        df_final['pontuacao_basica_atual'] = (
            (df_final['DS'] * 1.2) + 
            (df_final['DE'] * 1.0) + 
            (df_final['SG'] * 5.0) + 
            (df_final['FS'] * 0.5) + 
            (df_final['FD'] * 1.2) + 
            (df_final['FT'] * 3.0) + 
            (df_final['FF'] * 0.8) + 
            (df_final['PS'] * 1.0) + 
            (df_final['DP'] * 7.0)
        )
        
        return df_final

    df_agrupado = agrupar_dados(df_filtrado)
    
    # Base para Robô (Sem filtro de preço, mas com filtro de rodada/nome)
    df_base_robo = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]
    if somente_jogaram: df_base_robo = df_base_robo[df_base_robo['atletas.entrou_em_campo'] == True]
    if busca_nome: df_base_robo = df_base_robo[df_base_robo['atletas.apelido'].str.lower().str.contains(busca_nome)]
    
    df_robo_consolidado = agrupar_dados(df_base_robo)

    # ==========================================
    # --- VISUALIZAÇÃO ---
    # ==========================================
    if df_agrupado.empty:
        st.warning(f"⚠️ Nenhum jogador encontrado.")
    else:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador (Soma)", f"{df_agrupado['pontuacao_total_periodo'].max():.1f}")
        k2.metric("Média Geral (Por Jogo)", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
        k3.metric("Pontuação Básica (Acumulada)", f"{df_agrupado['pontuacao_basica_atual'].mean():.2f}")
        k4.metric("Jogadores Listados", f"{len(df_agrupado)}")

        st.markdown("---")

        tab_robo, tab_comparador, tab_capitao, tab_destaques, tab_adversario, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🤖 Robô Escalador", "⚔️ Comparador", "© Capitão de Segurança", "🏆 Destaques", 
            "🛡️ Raio-X Adversário", "📊 Times", "🏠 Casa vs Fora", "💎 Valorização", "📋 Tabela"
        ])

        # --- ROBÔ ESCALADOR ---
        with tab_robo:
            st.header("🤖 Otimizador com Orçamento Exato")
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
                                    if ratio < melhor_ratio:
                                        melhor_ratio = ratio
                                        melhor_troca = (idx, entrar)
                        if melhor_troca:
                            df_time = df_time.drop(melhor_troca[0])
                            df_time = pd.concat([df_time, melhor_troca[1].to_frame().T])
                            custo = df_time['atletas.preco_num'].sum()
                        else: break
                        loop += 1
                    
                    st.success(f"✅ Time Escalado! Custo: C$ {custo:.2f} | Saldo: C$ {orcamento - custo:.2f}")
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
                else: st.warning("Dados insuficientes para o esquema.")

        # --- ABA COMPARADOR ---
        with tab_comparador:
            st.header("⚔️ Comparador Mano a Mano")
            c1, c2 = st.columns(2)
            nomes = sorted(df_robo_consolidado['atletas.apelido'].unique())
            p1_n = c1.selectbox("Jogador 1", nomes, index=0)
            p2_n = c2.selectbox("Jogador 2", nomes, index=min(1, len(nomes)-1))
            
            if p1_n and p2_n:
                d1 = df_robo_consolidado[df_robo_consolidado['atletas.apelido'] == p1_n].iloc[0]
                d2 = df_robo_consolidado[df_robo_consolidado['atletas.apelido'] == p2_n].iloc[0]
                cats = ['Pontos Totais', 'Pontuação Básica', 'Gols', 'Assist', 'Finalizações', 'Desarmes']
                v1 = [d1['pontuacao_total_periodo'], d1['pontuacao_basica_atual'], d1['G'], d1['A'], d1['finalizacoes_total'], d1['DS']]
                v2 = [d2['pontuacao_total_periodo'], d2['pontuacao_basica_atual'], d2['G'], d2['A'], d2['finalizacoes_total'], d2['DS']]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(r=v1, theta=cats, fill='toself', name=p1_n, line_color='#00CC96', fillcolor='rgba(0, 204, 150, 0.5)'))
                fig.add_trace(go.Scatterpolar(r=v2, theta=cats, fill='toself', name=p2_n, line_color='#EF553B', fillcolor='rgba(239, 85, 59, 0.5)'))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True)), title="Comparativo Direto")
                st.plotly_chart(fig, use_container_width=True)

        # --- ABA CAPITÃO ---
        with tab_capitao:
            st.header("© Capitão de Segurança")
            if not df_jogos.empty:
                rds = sorted(df_jogos['rodada_id'].unique())
                rodada = st.selectbox("Simular Rodada:", rds)
                
                # Fragilidade Adversário (Geral)
                df_heat = df_filtrado[df_filtrado['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                
                # Jogos da rodada simulada
                jogos = df_jogos[df_jogos['rodada_id'] == rodada][['clube_id', 'Adversario', 'Mando_Padrao']]
                
                # Merge Jogadores x Próximo Jogo
                # Usa 'atletas.clube_id' que foi preservado no agrupar_dados
                df_cap = pd.merge(df_robo_consolidado, jogos, left_on='atletas.clube_id', right_on='clube_id', how='inner')
                
                if not df_cap.empty:
                    df_final = pd.merge(df_cap, df_heat, on=['Adversario', 'posicao_nome'], how='left')
                    df_final['media_cedida_adv'] = df_final['atletas.pontos_num'].fillna(0) # Rename result of merge
                    
                    # Score = (Pontuação Básica Acumulada + (Media Cedida * Jogos Jogados)) / 2 ???
                    # Não, vamos simplificar: Score = Pontuação Básica Média + Fragilidade Média
                    # Mas temos Pontuação Básica ACUMULADA. Vamos dividir por jogos para ter média.
                    # Mas seu df_grouped não tem 'jogos_num'. Vamos assumir que 'pontuacao_basica_atual' é força bruta.
                    # Vamos somar força bruta com fragilidade * peso.
                    
                    df_final['score_seguranca'] = df_final['pontuacao_basica_atual'] + (df_final['media_cedida_adv'] * 2) 
                    
                    st.dataframe(
                        df_final[['atletas.apelido', 'posicao_nome', 'Adversario', 'pontuacao_basica_atual', 'media_cedida_adv', 'score_seguranca']]
                        .sort_values('score_seguranca', ascending=False).head(20)
                        .rename(columns={'media_cedida_adv': 'Fragilidade Adv', 'pontuacao_basica_atual': 'Pont. Básica Jogador'}),
                        use_container_width=True, hide_index=True
                    )
                else: st.warning("Sem jogos previstos para os jogadores filtrados.")
            else: st.warning("Sem dados de confrontos.")

        # --- ABA DESTAQUES ---
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

        # --- ABA RAIO-X ---
        with tab_adversario:
            st.subheader("🔥 Raio-X: Quem cede mais pontos?")
            if 'Adversario' in df_filtrado.columns and not df_filtrado['Adversario'].isin(['N/A']).all():
                d = df_filtrado[df_filtrado['Adversario']!='N/A'].groupby(['Adversario','posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                def plot_h(pos, tit, cor):
                    dp = d[d['posicao_nome'].isin(pos)]
                    if dp.empty: return
                    p = dp.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                    p['T'] = p.sum(axis=1); p = p.sort_values('T').drop(columns='T')
                    st.plotly_chart(px.imshow(p, text_auto=".1f", color_continuous_scale=cor, title=tit), use_container_width=True)
                
                c1, c2, c3, c4 = st.columns(4)
                with c1: plot_h(['Goleiro'], "Gol", "Blues")
                with c2: plot_h(['Zagueiro','Lateral'], "Defesa", "Greens")
                with c3: plot_h(['Meia'], "Meia", "Oranges")
                with c4: plot_h(['Atacante'], "Ataque", "Reds")

        # --- DEMAIS ABAS (Mantidas Simplificadas) ---
        with tab_times:
            g = df_filtrado.groupby('atletas.clube.id.full.name')[['atletas.pontos_num', 'finalizacoes_total']].mean().reset_index()
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.bar(g.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h', title="Média Pontos"), use_container_width=True)
            c2.plotly_chart(px.bar(g.sort_values('finalizacoes_total'), x='finalizacoes_total', y='atletas.clube.id.full.name', orientation='h', title="Média Finalizações", color_discrete_sequence=['red']), use_container_width=True)

        with tab_scouts:
            if 'Mando_Padrao' in df_filtrado.columns:
                g = df_filtrado.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                st.plotly_chart(px.bar(g, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group', title="Ofensivo"), use_container_width=True)

        with tab_valorizacao:
            st.plotly_chart(px.scatter(df_filtrado, x='atletas.preco_num', y='atletas.pontos_num', color='posicao_nome', size='tamanho_visual', hover_name='atletas.apelido', title="Preço x Pontuação"), use_container_width=True)

        with tab_tabela:
            st.subheader("Tabela Consolidada")
            cols = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.preco_num', 'pontuacao_total_periodo', 'pontuacao_basica_atual'] + todos_scouts
            st.dataframe(df_agrupado[cols].sort_values('pontuacao_total_periodo', ascending=False), use_container_width=True, hide_index=True)
